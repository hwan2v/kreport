# app/core/logging.py
import os
import json
import logging
import logging.config
from logging.handlers import TimedRotatingFileHandler
from contextvars import ContextVar
from datetime import datetime

# ===== Request ID =====
request_id_ctx = ContextVar("request_id", default="-")

class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True

# ===== JSON Formatter =====
class JsonFormatter(logging.Formatter):
    """
    JSON 라인 출력: Logstash에서 바로 파싱 가능.
    uvicorn.access 레코드에 존재할 수 있는 필드들도 안전하게 포함.
    """
    def format(self, record: logging.LogRecord) -> str:
        # 기본 필드
        payload = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        # 예외 스택
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # uvicorn.access 특화 필드(있으면 포함)
        for k in (
            "client_addr", "request_line", "status_code",
            "http_method", "http_version", "path", "query_string",
            "client_ip", "user_agent", "duration_ms", "scheme",
        ):
            v = getattr(record, k, None)
            if v is not None:
                payload[k] = v

        return json.dumps(payload, ensure_ascii=False)

# ===== Text Formatter (로컬 확인용) =====
TEXT_DEFAULT = "%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s"

def setup_logging(
    *,
    log_to_file: bool = False,
    log_dir: str = "/var/log/app",
    as_json: bool = True,
    level: str = "INFO",
) -> None:
    """
    - app 로그: root, uvicorn.error
    - access 로그: uvicorn.access
    - 중복 방지: uvicorn.* 는 propagate=False
    """
    os.environ.setdefault("TZ", "UTC")  # 타임존 명시 (로그 일관성)

    # 포맷터
    formatters = {
        "json": {"()": JsonFormatter},
        "text_default": {"format": TEXT_DEFAULT},
        "text_access": {"format": "%(asctime)s %(levelname)s [access] [%(request_id)s] %(message)s"},
    }

    # 핸들러(콘솔)
    handlers = {
        "console_app": {
            "class": "logging.StreamHandler",
            "level": level,
            "formatter": "json" if as_json else "text_default",
            "filters": ["request_id"],
        },
        "console_access": {
            "class": "logging.StreamHandler",
            "level": level,
            "formatter": "json" if as_json else "text_access",
            "filters": ["request_id"],
        },
    }

    # 핸들러(파일, 선택)
    if log_to_file:
        os.makedirs(log_dir, exist_ok=True)
        handlers["file_app"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": level,
            "formatter": "json" if as_json else "text_default",
            "filename": f"{log_dir}/app.log",
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "filters": ["request_id"],
        }
        handlers["file_access"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": level,
            "formatter": "json" if as_json else "text_access",
            "filename": f"{log_dir}/access.log",
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "filters": ["request_id"],
        }

    # 루트/uvicorn 로거 설정
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,

        "filters": {
            "request_id": {"()": RequestIDFilter}
        },

        "formatters": formatters,
        "handlers": handlers,

        "loggers": {
            # 애플리케이션(루트)
            "": {
                "handlers": ["console_app"] + (["file_app"] if log_to_file else []),
                "level": level,
                "propagate": False,
            },
            # Uvicorn 내부 에러/서버 로그 (app 로그에 포함)
            "uvicorn.error": {
                "handlers": ["console_app"] + (["file_app"] if log_to_file else []),
                "level": level,
                "propagate": False,
            },
            # 접근 로그는 별도 핸들러로 (access 지표 집계를 위해 분리)
            "uvicorn.access": {
                "handlers": ["console_access"] + (["file_access"] if log_to_file else []),
                "level": level,
                "propagate": False,
            },
        },
    })
