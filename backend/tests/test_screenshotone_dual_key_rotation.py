"""Comprehensive tests for ScreenshotOne dual-key round-robin rotation, failover, and persistence."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.integrations.screenshotone.client import (
    ScreenshotOneClient,
    ScreenshotOneAPIError,
    ScreenshotOneConfigurationError,
)
from app.integrations.screenshotone.key_manager import KeyState, ScreenshotOneKeyManager


def test_key_state_lifecycle():
    state = KeyState(slot_id=1, key="SECRET_KEY_123456789")
    assert state.is_eligible() is True
    assert state.usage_count == 0

    state.mark_success()
    assert state.usage_count == 1
    assert state.last_used_at is not None

    # Test 429 quota cooldown
    state.mark_exhausted(cooldown_seconds=10.0)
    assert state.is_exhausted is True
    assert state.is_eligible() is False
    assert state.error_count == 1

    # Sanitized status output never leaks raw key
    info = state.to_dict()
    assert "SECRET_KEY_123456789" not in str(info)
    assert info["masked_key"] == "SECR...6789"
    assert info["status"] == "exhausted"


def test_key_manager_deterministic_round_robin(tmp_path: Path):
    state_file = tmp_path / "test_rotation.json"
    km = ScreenshotOneKeyManager(
        key_1="KEY_ALPHA_12345",
        key_2="KEY_BETA_67890",
        state_file=state_file,
    )
    assert km.total_configured_keys == 2
    assert km.is_configured() is True

    # Deterministic sequence: Slot 1 -> Slot 2 -> Slot 1 -> Slot 2
    slot_a, key_a = km.get_next_key()
    assert slot_a == 1
    assert key_a == "KEY_ALPHA_12345"

    slot_b, key_b = km.get_next_key()
    assert slot_b == 2
    assert key_b == "KEY_BETA_67890"

    slot_c, key_c = km.get_next_key()
    assert slot_c == 1
    assert key_c == "KEY_ALPHA_12345"

    slot_d, key_d = km.get_next_key()
    assert slot_d == 2
    assert key_d == "KEY_BETA_67890"


def test_key_manager_persistence_across_instances(tmp_path: Path):
    state_file = tmp_path / "test_persistence.json"

    # Instance 1 uses Slot 1
    km1 = ScreenshotOneKeyManager(
        key_1="KEY_ALPHA_12345",
        key_2="KEY_BETA_67890",
        state_file=state_file,
    )
    slot1, _ = km1.get_next_key()
    assert slot1 == 1

    # Instance 2 (simulating restart) should pick up next slot (Slot 2)
    km2 = ScreenshotOneKeyManager(
        key_1="KEY_ALPHA_12345",
        key_2="KEY_BETA_67890",
        state_file=state_file,
    )
    slot2, _ = km2.get_next_key()
    assert slot2 == 2


def test_key_manager_single_key_fallback(tmp_path: Path):
    # Only Key 1 configured
    km = ScreenshotOneKeyManager(
        key_1="ONLY_KEY_12345",
        key_2=None,
        legacy_key=None,
        state_file=tmp_path / "test_single.json",
    )
    assert km.total_configured_keys == 1
    slot, key = km.get_next_key()
    assert slot == 1
    assert key == "ONLY_KEY_12345"

    # Subsequent request uses the same key without error
    slot2, key2 = km.get_next_key()
    assert slot2 == 1
    assert key2 == "ONLY_KEY_12345"


@pytest.mark.asyncio
async def test_key_manager_concurrency(tmp_path: Path):
    km = ScreenshotOneKeyManager(
        key_1="CONCURRENT_KEY_1",
        key_2="CONCURRENT_KEY_2",
        state_file=tmp_path / "test_concurrent.json",
    )

    async def worker():
        await asyncio.sleep(0.001)
        return km.get_next_key()[0]

    tasks = [worker() for _ in range(20)]
    results = await asyncio.gather(*tasks)

    # 10 from Slot 1, 10 from Slot 2
    assert results.count(1) == 10
    assert results.count(2) == 10


@pytest.mark.asyncio
async def test_client_rotation_and_failover_on_429(tmp_path: Path):
    km = ScreenshotOneKeyManager(
        key_1="PRIMARY_KEY_429",
        key_2="BACKUP_KEY_OK",
        state_file=tmp_path / "test_failover_429.json",
    )
    client = ScreenshotOneClient(key_manager=km)

    fake_image_bytes = b"IMAGE_DATA_SUCCESS"

    def mock_post_side_effect(url, params=None, data=None, **kwargs):
        access_key = params.get("access_key")
        if access_key == "PRIMARY_KEY_429":
            # Key 1 returns 429 quota exhaustion
            return httpx.Response(
                status_code=429,
                json={"error": {"code": "quota_exceeded", "message": "Monthly credit exhausted"}},
                request=httpx.Request("POST", url),
            )
        else:
            # Key 2 succeeds
            return httpx.Response(
                status_code=200,
                content=fake_image_bytes,
                headers={"content-type": "image/jpeg"},
                request=httpx.Request("POST", url),
            )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = mock_post_side_effect

        result = await client.render_html("<html><body>Card</body></html>")

        assert result == fake_image_bytes
        # Verified that both keys were called: Key 1 failed with 429, Key 2 succeeded
        assert mock_post.call_count == 2
        calls = mock_post.call_args_list
        assert calls[0].kwargs["params"]["access_key"] == "PRIMARY_KEY_429"
        assert calls[1].kwargs["params"]["access_key"] == "BACKUP_KEY_OK"

    # Status check confirms Key 1 is exhausted, Key 2 is active
    status = client.get_rotation_status()
    assert status["slots"][0]["status"] == "exhausted"
    assert status["slots"][1]["status"] == "active"
    assert status["slots"][1]["usage_count"] == 1


@pytest.mark.asyncio
async def test_client_failover_on_401_auth_error(tmp_path: Path):
    km = ScreenshotOneKeyManager(
        key_1="EXPIRED_KEY_401",
        key_2="VALID_KEY_OK",
        state_file=tmp_path / "test_failover_401.json",
    )
    client = ScreenshotOneClient(key_manager=km)
    fake_image_bytes = b"IMAGE_DATA_AUTH_FAILOVER"

    def mock_post_side_effect(url, params=None, data=None, **kwargs):
        access_key = params.get("access_key")
        if access_key == "EXPIRED_KEY_401":
            return httpx.Response(
                status_code=401,
                json={"error": {"code": "invalid_access_key", "message": "Access key revoked"}},
                request=httpx.Request("POST", url),
            )
        else:
            return httpx.Response(
                status_code=200,
                content=fake_image_bytes,
                headers={"content-type": "image/jpeg"},
                request=httpx.Request("POST", url),
            )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = mock_post_side_effect

        result = await client.render_html("<html><body>Card</body></html>")
        assert result == fake_image_bytes
        assert mock_post.call_count == 2

    status = client.get_rotation_status()
    assert status["slots"][0]["status"] == "invalid"
    assert status["slots"][1]["status"] == "active"


@pytest.mark.asyncio
async def test_client_both_keys_exhausted_raises_error(tmp_path: Path):
    km = ScreenshotOneKeyManager(
        key_1="KEY_1_FAILS",
        key_2="KEY_2_FAILS",
        state_file=tmp_path / "test_both_fail.json",
    )
    client = ScreenshotOneClient(key_manager=km)

    def mock_post_side_effect(url, params=None, data=None, **kwargs):
        return httpx.Response(
            status_code=429,
            json={"error": {"code": "rate_limit", "message": "Too many requests"}},
            request=httpx.Request("POST", url),
        )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = mock_post_side_effect

        with pytest.raises(ScreenshotOneAPIError) as exc_info:
            await client.render_html("<html><body>Card</body></html>")

        assert exc_info.value.status_code == 429
        # Both keys attempted once
        assert mock_post.call_count == 2
        # Error message never contains raw keys
        assert "KEY_1_FAILS" not in str(exc_info.value)
        assert "KEY_2_FAILS" not in str(exc_info.value)
