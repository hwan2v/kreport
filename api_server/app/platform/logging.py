# app/core/logging.py
import os
import logging
import logging.config
from logging.handlers import TimedRotatingFileHandler
from contextvars import ContextVar

# 요청별 trace id 저장
request_id_ctx = ContextVar("request_id", default="-")

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx.get()
        return True

def setup_logging(log_to_file: bool = False, log_dir: str = "./logs"):
    handlers: dict[str, dict] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "filters": ["request_id"],
        }
    }

    if log_to_file:
        os.makedirs(log_dir, exist_ok=True)
        handlers["app_file"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "INFO",
            "formatter": "default",
            "filename": f"{log_dir}/app.log",
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "filters": ["request_id"],
        }
        handlers["access_file"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "INFO",
            "formatter": "access",
            "filename": f"{log_dir}/access.log",
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "filters": ["request_id"],
        }

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,

        "filters": {
            "request_id": {"()": RequestIDFilter}
        },

        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s"
            },
            "access": {
                "format": "%(asctime)s %(levelname)s [access] [%(request_id)s] %(message)s"
            },
        },

        "handlers": handlers,

        "loggers": {
            # 애플리케이션 로거
            "": {
                "handlers": list(handlers.keys()),
                "level": "INFO",
            },
            # uvicorn 자체 로거들
            "uvicorn.error": {
                "handlers": list(handlers.keys()),
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.access": {
                "handlers": (["console"] + (["access_file"] if log_to_file else [])),
                "level": "INFO",
                "propagate": False
            },
        },
    })
