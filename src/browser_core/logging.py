# Fornece um sistema de logging estruturado e configurável para o framework.
#
# Este módulo é adaptado para o ciclo de vida de tarefas efêmeras,
# suportando logging hierárquico com um arquivo consolidado e arquivos
# individuais para cada worker.

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING, Union

from .types import FilePath, LoggingConfig
from .utils import ensure_directory, mask_sensitive_data

if TYPE_CHECKING:
    from .worker import Worker


class StructuredFormatter(logging.Formatter):
    """
    Formatter de log customizado que suporta múltiplos formatos (JSON, detalhado).
    """

    def __init__(self, format_type: str = "detailed", mask_credentials: bool = True):
        self.format_type = format_type
        self.mask_credentials = mask_credentials
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Formata o registo de log, aplicando máscaras e o formato escolhido."""
        if self.mask_credentials and isinstance(record.msg, str):
            record.msg = mask_sensitive_data(str(record.msg))

        if self.format_type == "json":
            return self._format_json(record)

        return self._format_detailed(record)

    def _format_json(self, record: logging.LogRecord) -> str:
        """Formata a saída de log como uma única linha JSON estruturada."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        extra_fields = ["task_id", "snapshot_id", "tab_name"]
        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)

    def _format_detailed(self, record: logging.LogRecord) -> str:
        """Formata a saída de log de forma legível para humanos."""
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # O nome do logger (ex: browser_core.task.worker_0) já identifica o worker.
        context_parts = [record.name]
        if hasattr(record, "tab_name"):
            context_parts.append(f"tab={getattr(record, 'tab_name')}")

        context_str = f" [{', '.join(context_parts)}]"
        return f"{timestamp} [{record.levelname}] {record.getMessage()}{context_str}"


class TaskLoggerAdapter(logging.LoggerAdapter):
    """
    Um LoggerAdapter que injeta automaticamente o contexto da tarefa
    (como o nome da aba) em cada mensagem de log.
    """

    def __init__(self, logger: logging.Logger, extra: Dict[str, Any]):
        super().__init__(logger, extra)
        self.worker_instance: Optional["Worker"] = None

    def process(self, msg: Any, kwargs: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Processa a mensagem de log para injetar o contexto dinâmico."""
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        kwargs["extra"].update(self.extra)

        if self.worker_instance and self.worker_instance._is_started:
            try:
                if current_tab := self.worker_instance.current_tab:
                    kwargs["extra"]["tab_name"] = current_tab.name
            except Exception:
                pass  # Evita que uma falha no logging quebre a aplicação.

        return msg, kwargs


def setup_task_logger(
        logger_name: str,
        log_dir: Path,
        config: LoggingConfig,
        consolidated_handler: Optional[logging.Handler] = None
) -> TaskLoggerAdapter:
    """
    Cria e configura um logger específico para uma única tarefa/worker.

    Args:
        logger_name: O nome para o logger (ex: 'worker_0').
        log_dir: O diretório onde o arquivo de log individual será guardado.
        config: O dicionário de configuração para os logs.
        consolidated_handler: Um handler opcional compartilhado para o log consolidado.
    """
    logger = logging.getLogger(f"browser_core.task.{logger_name}")
    logger.propagate = False
    logger.setLevel(config.get("level", "INFO").upper())

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = StructuredFormatter(
        format_type=config.get("format_type", "detailed"),
        mask_credentials=config.get("mask_credentials", True),
    )

    # Adiciona o handler para o arquivo de log individual do worker
    if config.get("to_file", True) and log_dir:
        individual_log_path = log_dir / f"{logger_name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            filename=individual_log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Adiciona o handler compartilhado para o log consolidado, se fornecido
    if consolidated_handler:
        logger.addHandler(consolidated_handler)

    if config.get("to_console", False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return TaskLoggerAdapter(logger, {"task_id": logger_name})
