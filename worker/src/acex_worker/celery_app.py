"""Celery entry point: `celery -A acex_worker.celery_app worker -Q acex.default,acex.provision`."""

from acex.messaging import celery_app as app

__all__ = ["app"]
