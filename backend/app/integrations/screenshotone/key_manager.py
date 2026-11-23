"""ScreenshotOne Dual-Key Rotation and Health Management.

Implements deterministic round-robin rotation across two configured ScreenshotOne API key slots,
concurrency safety, persistent state across restarts, health and quota tracking,
graceful single-key fallback, and failover recovery without exposing credentials.
"""

import asyncio
import datetime
import json
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.social.base import mask_secret


class KeyState:
    """Tracks runtime operational state and health for a single key slot."""

    def __init__(self, slot_id: int, key: str):
        self.slot_id = slot_id
        self.key = key
        self.is_exhausted: bool = False
        self.exhausted_until: Optional[datetime.datetime] = None
        self.is_invalid: bool = False
        self.invalid_until: Optional[datetime.datetime] = None
        self.usage_count: int = 0
        self.error_count: int = 0
        self.last_used_at: Optional[datetime.datetime] = None

    def is_eligible(self) -> bool:
        """Determines whether the key is currently healthy and eligible for requests."""
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.is_invalid:
            if self.invalid_until and now >= self.invalid_until:
                self.is_invalid = False
                self.invalid_until = None
            else:
                return False

        if self.is_exhausted:
            if self.exhausted_until and now >= self.exhausted_until:
                self.is_exhausted = False
                self.exhausted_until = None
            else:
                return False

        return True

    def mark_success(self) -> None:
        """Records a successful render request."""
        self.usage_count += 1
        self.last_used_at = datetime.datetime.now(datetime.timezone.utc)
        self.is_exhausted = False
        self.exhausted_until = None

    def mark_exhausted(self, cooldown_seconds: float = 60.0) -> None:
        """Records HTTP 429 quota exhaustion or rate limit with temporary cooldown."""
        self.is_exhausted = True
        self.error_count += 1
        self.exhausted_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=cooldown_seconds
        )

    def mark_invalid(self, cooldown_seconds: float = 300.0) -> None:
        """Records HTTP 401/403 authorization failure with temporary cooldown."""
        self.is_invalid = True
        self.error_count += 1
        self.invalid_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=cooldown_seconds
        )

    def to_dict(self) -> Dict[str, Any]:
        """Returns a sanitized snapshot of key health. Strictly never exposes the raw key."""
        now = datetime.datetime.now(datetime.timezone.utc)
        status = "active"
        if self.is_invalid:
            status = "invalid"
        elif self.is_exhausted:
            status = "exhausted"

        return {
            "slot_id": self.slot_id,
            "masked_key": mask_secret(self.key),
            "status": status,
            "is_eligible": self.is_eligible(),
            "usage_count": self.usage_count,
            "error_count": self.error_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "cooldown_remaining_seconds": (
                max(0.0, ((self.invalid_until or self.exhausted_until) - now).total_seconds())
                if (self.invalid_until or self.exhausted_until)
                else 0.0
            ),
        }


class ScreenshotOneKeyManager:
    """Manages deterministic round-robin rotation and failover between ScreenshotOne API keys.
    
    Guarantees:
    - Never logs, prints, or exposes raw API keys.
    - Enforces deterministic round-robin ordering (Slot 1 -> Slot 2 -> Slot 1 -> Slot 2).
    - Falls back to single-key mode gracefully if only one slot is configured.
    - Persists last-used slot index across application restarts where practical.
    - Concurrency-safe across threads and async tasks.
    - Provides automatic failover on 429/401/403.
    """

    def __init__(
        self,
        key_1: Optional[str] = None,
        key_2: Optional[str] = None,
        legacy_key: Optional[str] = None,
        state_file: Optional[Path] = None,
    ):
        raw_keys: List[str] = []
        explicit_passed = (key_1 is not None or key_2 is not None or legacy_key is not None)
        if explicit_passed:
            k1 = key_1
            k2 = key_2
            k_legacy = legacy_key
        else:
            k1 = settings.SCREENSHOTONE_ACCESS_KEY_1
            k2 = settings.SCREENSHOTONE_ACCESS_KEY_2
            k_legacy = settings.SCREENSHOTONE_ACCESS_KEY

        # Collect configured keys in deterministic order
        if k1 and k1.strip():
            raw_keys.append(k1.strip())
        if k2 and k2.strip():
            # Avoid duplicate if same key entered twice
            if not raw_keys or k2.strip() != raw_keys[0]:
                raw_keys.append(k2.strip())

        # If slot 1/2 were not set, check legacy single key
        if not raw_keys and k_legacy and k_legacy.strip():
            raw_keys.append(k_legacy.strip())

        self._states: List[KeyState] = [
            KeyState(slot_id=idx + 1, key=k) for idx, k in enumerate(raw_keys)
        ]
        self._key_to_state: Dict[str, KeyState] = {s.key: s for s in self._states}

        # Concurrency primitives
        self._thread_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

        # State persistence
        if state_file:
            self._state_file = state_file
        else:
            # Default persistent state location in backend root
            self._state_file = Path(__file__).resolve().parent.parent.parent.parent / ".screenshotone_rotation_state"

        # Load initial rotation index
        self._current_index = self._load_persisted_index()

    @property
    def total_configured_keys(self) -> int:
        return len(self._states)

    def is_configured(self) -> bool:
        """Returns True if at least one valid key slot is configured."""
        return len(self._states) > 0

    def _load_persisted_index(self) -> int:
        """Reads persisted rotation index from disk safely."""
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                idx = int(data.get("last_index", 0))
                if 0 <= idx < max(1, len(self._states)):
                    return idx
        except Exception as exc:
            logger.debug(f"[SCREENSHOTONE] Could not load persisted rotation state: {exc}")
        return 0

    def _persist_index(self, idx: int) -> None:
        """Persists rotation index to disk safely."""
        try:
            self._state_file.write_text(
                json.dumps({"last_index": idx, "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug(f"[SCREENSHOTONE] Could not persist rotation state: {exc}")

    def get_next_key(self) -> Tuple[int, str]:
        """Selects the next eligible key in deterministic round-robin sequence.
        
        Returns:
            Tuple[int, str]: (slot_id, raw_key)
            
        Raises:
            RuntimeError: If no keys are configured.
            RuntimeError: If all configured keys are currently exhausted or invalid.
        """
        with self._thread_lock:
            if not self._states:
                raise RuntimeError("No ScreenshotOne API keys are configured.")

            total = len(self._states)
            if total == 1:
                state = self._states[0]
                if not state.is_eligible():
                    status_desc = "exhausted (quota/rate limit)" if state.is_exhausted else "invalid"
                    raise RuntimeError(
                        f"ScreenshotOne single key slot {state.slot_id} is currently {status_desc}."
                    )
                return state.slot_id, state.key

            # Round-robin selection starting from next sequential index
            # Check up to `total` candidates in round-robin order
            candidate_indices = [(self._current_index + i) % total for i in range(total)]

            selected_state: Optional[KeyState] = None
            for idx in candidate_indices:
                cand = self._states[idx]
                if cand.is_eligible():
                    selected_state = cand
                    # Advance rotation index to the next slot for the subsequent request
                    self._current_index = (idx + 1) % total
                    self._persist_index(self._current_index)
                    break

            if selected_state is None:
                # All keys in cooldown. Determine if any 429 can be retried immediately
                for cand in self._states:
                    if not cand.is_invalid:  # 429 only
                        selected_state = cand
                        self._current_index = (cand.slot_id) % total
                        self._persist_index(self._current_index)
                        break

            if selected_state is None:
                raise RuntimeError(
                    "All configured ScreenshotOne API key slots are currently exhausted or invalid."
                )

            return selected_state.slot_id, selected_state.key

    def get_alternative_key(self, failed_key: str) -> Optional[Tuple[int, str]]:
        """Finds another eligible key slot distinct from the failed key.
        
        Used for immediate in-flight failover upon receiving 429 or 401/403.
        """
        with self._thread_lock:
            for state in self._states:
                if state.key != failed_key and state.is_eligible():
                    return state.slot_id, state.key
            # If all others in cooldown, check any that is not invalid
            for state in self._states:
                if state.key != failed_key and not state.is_invalid:
                    return state.slot_id, state.key
            return None

    def mark_success(self, key: str) -> None:
        """Records successful response for the specified key."""
        with self._thread_lock:
            state = self._key_to_state.get(key)
            if state:
                state.mark_success()

    def mark_exhausted(self, key: str, cooldown_seconds: float = 60.0) -> None:
        """Marks key as exhausted (HTTP 429)."""
        with self._thread_lock:
            state = self._key_to_state.get(key)
            if state:
                state.mark_exhausted(cooldown_seconds=cooldown_seconds)
                logger.warning(
                    f"[SCREENSHOTONE] Key slot {state.slot_id} marked exhausted for {cooldown_seconds}s (HTTP 429)."
                )

    def mark_invalid(self, key: str, cooldown_seconds: float = 300.0) -> None:
        """Marks key as invalid (HTTP 401/403)."""
        with self._thread_lock:
            state = self._key_to_state.get(key)
            if state:
                state.mark_invalid(cooldown_seconds=cooldown_seconds)
                logger.warning(
                    f"[SCREENSHOTONE] Key slot {state.slot_id} marked invalid for {cooldown_seconds}s (HTTP 401/403)."
                )

    def reset_states(self) -> None:
        """Resets all runtime states and cooldowns (useful for tests or manual operator override)."""
        with self._thread_lock:
            for s in self._states:
                s.is_exhausted = False
                s.exhausted_until = None
                s.is_invalid = False
                s.invalid_until = None
                s.error_count = 0
            self._current_index = 0

    def get_status(self) -> Dict[str, Any]:
        """Provides a sanitized summary of all managed key slots. Never exposes keys."""
        with self._thread_lock:
            slots = [s.to_dict() for s in self._states]
            return {
                "total_slots": len(self._states),
                "is_configured": self.is_configured(),
                "current_slot_index": self._current_index + 1 if self._states else 0,
                "slots": slots,
            }
