import asyncio
import signal
import sys
from app.core.config import settings
from app.core.logging import logger
from app.workers.scheduler import create_scheduler


class NewsWorkerService:
    """Manages the background news discovery worker lifecycle."""

    def __init__(self):
        self.scheduler = create_scheduler()
        self.running = False

    async def start(self) -> None:
        logger.info("Initializing MetroScope News Discovery Worker...")
        if not settings.WORKER_ENABLED:
            logger.warning("Worker disabled via WORKER_ENABLED setting. Exiting.")
            return

        self.scheduler.start()
        self.running = True
        logger.info("MetroScope News Discovery Worker is running.")

        # Keep running until stop requested
        while self.running:
            await asyncio.sleep(1)

    def stop(self) -> None:
        logger.info("Stopping MetroScope News Discovery Worker...")
        self.running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("News Worker stopped cleanly.")


async def main() -> None:
    service = NewsWorkerService()

    def handle_signal():
        service.stop()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows compatibility for signal handlers
            pass

    try:
        await service.start()
    except (KeyboardInterrupt, SystemExit):
        service.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker process terminated.")
        sys.exit(0)
