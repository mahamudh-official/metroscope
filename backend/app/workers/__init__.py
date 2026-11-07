"""News worker package for background discovery tasks."""

from app.workers.scheduler import create_scheduler

__all__ = ["create_scheduler"]
