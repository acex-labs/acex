"""Logging configuration for the API service.

Mirrors uvicorn's default LOGGING_CONFIG, but with timestamps in every
record and a root logger so the backend's own `acex.*` loggers get
formatted output too (uvicorn's default config leaves them handlerless,
silently dropping INFO logs and printing WARNING+ unformatted).

The root logger sits at INFO, so INFO records from third-party libraries
(alembic, sqlalchemy, httpx, watchfiles in --reload mode) are now emitted
as well; raise their levels in `loggers` below if that gets noisy.
"""

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s %(levelprefix)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": None,  # auto: colors in a TTY, plain in containers
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": None,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
    "root": {"level": "INFO", "handlers": ["default"]},
}
