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
from typing import Any, Dict, Tuple

from .types import FilePath, LoggingConfig
from .utils import ensure_directory, mask_sensitive_data


class StructuredFormatter(logging.Formatter):
    """
    Formatter de log customizado que suporta múltiplos formatos (JSON, detalhado).

    Formata os registos de log em JSON para consumo por máquinas ou num
    formato de texto detalhado para leitura humana, baseado na configuração.
    """

    def __init__(self, format_type: str = "detailed", mask_credentials: bool = True):
        self.format_type = format_type
        self.mask_credentials = mask_credentials
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        # Garante que dados sensíveis sejam mascarados antes de formatar a mensagem.
        if self.mask_credentials and isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)

        if self.format_type == "json":
            return self._format_json(record)

        # O formato detalhado é o padrão.
        return self._format_detailed(record)

    def _format_json(self, record: logging.LogRecord) -> str:
        # Formata o registo de log como uma string JSON estruturada.
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Adiciona campos extras ao log, se existirem, para enriquecer o contexto.
        extra_fields = ["session_id", "username"]
        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)

    def _format_detailed(self, record: logging.LogRecord) -> str:
        # Formata o registo de log num formato detalhado e legível para humanos.
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        context_parts = []
        if hasattr(record, "session_id"):
            context_parts.append(f"session={record.session_id}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        return f"{timestamp} [{record.levelname:<8}] {record.name}: {record.getMessage()}{context_str}"


class SessionLoggerAdapter(logging.LoggerAdapter):
    """
    Um LoggerAdapter que injeta automaticamente o contexto da sessão
    (como session_id e username) em cada mensagem de log.
    """

    def process(self, msg: Any, kwargs: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        # Adiciona os dados da sessão ao dicionário 'extra' do registo de log.
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        if isinstance(self.extra, dict):
            kwargs["extra"]["session_id"] = self.extra.get("session_id")
            kwargs["extra"]["username"] = self.extra.get("username")

        return msg, kwargs


def setup_session_logger(
        session_id: str,
        username: str,
        logs_dir: FilePath,
        config: LoggingConfig,
) -> logging.LoggerAdapter:
    """
    Cria e configura um logger específico para uma sessão de automação.

    Args:
        session_id: O ID único da sessão.
        username: O nome do utilizador associado à sessão.
        logs_dir: O diretório onde o ficheiro de log da sessão será salvo.
        config: Um dicionário de configuração de logging (LoggingConfig).

    Returns:
        Uma instância de LoggerAdapter com o contexto da sessão já configurado.
    """
    logger_name = f"browser.session.{session_id}"
    logger = logging.getLogger(logger_name)

    # Previne a propagação de logs para o logger raiz, evitando duplicação.
    logger.propagate = False
    logger.setLevel(config.get("level", "INFO").upper())

    # Limpa handlers existentes para evitar configuração duplicada em reexecuções.
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = StructuredFormatter(
        format_type=config.get("format_type", "detailed"),
        mask_credentials=config.get("mask_credentials", True),
    )

    # Configura o handler para a consola, se habilitado.
    if config.get("to_console", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Configura o handler para o ficheiro, se habilitado.
    if config.get("to_file", True):
        log_path = Path(logs_dir) / f"{session_id}.log"
        ensure_directory(log_path.parent)

        # Usa RotatingFileHandler para controlar o tamanho máximo dos ficheiros de log.
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Retorna um LoggerAdapter para injetar o contexto da sessão automaticamente.
    return SessionLoggerAdapter(logger, {"session_id": session_id, "username": username})
