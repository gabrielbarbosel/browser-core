# Fornece um sistema de logging estruturado e configurável para o framework.
#
# Este módulo implementa um sistema de logs que é 'thread-safe', permitindo
# o uso em aplicações concorrentes. Suporta múltiplos formatos de saída,
# incluindo JSON para integração com sistemas de monitorização, e o
# mascaramento automático de dados sensíveis.

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, TYPE_CHECKING

from .types import FilePath, LoggingConfig
from .utils import ensure_directory, mask_sensitive_data

# Evita importação circular, mas permite o type hinting
if TYPE_CHECKING:
    from .browser import Browser


class StructuredFormatter(logging.Formatter):
    """
    Formatter de log customizado que suporta múltiplos formatos (JSON, detalhado).
    """

    def __init__(self, format_type: str = "detailed", mask_credentials: bool = True):
        self.format_type = format_type
        self.mask_credentials = mask_credentials
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        if self.mask_credentials and isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)

        if self.format_type == "json":
            return self._format_json(record)

        return self._format_detailed(record)

    def _format_json(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        extra_fields = ["session_id", "username", "tab_name"]
        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)

    def _format_detailed(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        context_parts = []
        if hasattr(record, "session_id"):
            context_parts.append(f"session={record.session_id}")
        if hasattr(record, "tab_name"):
            context_parts.append(f"tab={record.tab_name}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        return f"{timestamp} [{record.levelname:<8}] {record.name}: {record.getMessage()}{context_str}"


class SessionLoggerAdapter(logging.LoggerAdapter):
    """
    Um LoggerAdapter que injeta automaticamente o contexto da sessão
    (como session_id, username e nome da aba) em cada mensagem de log.
    """

    def __init__(self, logger, extra):
        super().__init__(logger, extra)
        self.browser_instance: Optional["Browser"] = None

    def process(self, msg: Any, kwargs: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        if isinstance(self.extra, dict):
            kwargs["extra"]["session_id"] = self.extra.get("session_id")
            kwargs["extra"]["username"] = self.extra.get("username")

        if self.browser_instance and self.browser_instance._is_started:
            try:
                current_tab = self.browser_instance.current_tab
                if current_tab:
                    kwargs["extra"]["tab_name"] = current_tab.name
            except Exception:
                pass

        return msg, kwargs


def setup_session_logger(
        session_id: str,
        username: str,
        logs_dir: FilePath,
        config: LoggingConfig,
) -> SessionLoggerAdapter:
    """
    Cria e configura um logger específico para uma sessão de automação.
    """
    logger_name = f"browser_core.session.{session_id}"
    logger = logging.getLogger(logger_name)

    logger.propagate = False
    logger.setLevel(config.get("level", "INFO").upper())

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = StructuredFormatter(
        format_type=config.get("format_type", "detailed"),
        mask_credentials=config.get("mask_credentials", True),
    )

    if config.get("to_console", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if config.get("to_file", True):
        log_path = Path(logs_dir) / f"{session_id}.log"
        ensure_directory(log_path.parent)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return SessionLoggerAdapter(logger, {"session_id": session_id, "username": username})
