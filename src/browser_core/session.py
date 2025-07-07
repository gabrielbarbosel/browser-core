# Define o sistema de gestão de sessão de automação.
#
# Este módulo é responsável por gerir o ciclo de vida de uma única
# execução da automação, incluindo a criação de diretórios, a gestão
# de logs e a captura de snapshots para aquela sessão específica.

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .exceptions import SnapshotError
from .logging import setup_session_logger
from .types import (
    LoggingConfig,
    SessionData,
    SessionPathConfig,
    SnapshotConfig,
    SnapshotData,
    UserProfileProtocol,
    WebDriverProtocol,
)
from .utils import ensure_directory, generate_session_id, safe_json_dumps


class SessionManager:
    """
    Gere uma sessão de automação individual e os seus artefactos.

    Cada sessão representa uma única execução do navegador e contém os seus
    próprios logs, snapshots e outros dados gerados.
    """

    def __init__(
            self,
            username: str,
            profile_manager: UserProfileProtocol,
            logging_settings: LoggingConfig,
            snapshot_settings: SnapshotConfig,
            session_id: Optional[str] = None,
    ):
        """
        Inicializa o gestor de sessão.

        Args:
            username: O nome do utilizador associado à sessão.
            profile_manager: A instância do gestor de perfis que criou esta sessão.
            logging_settings: O dicionário de configuração para os logs.
            snapshot_settings: O dicionário de configuração para os snapshots.
            session_id: Um ID de sessão opcional para ser usado. Se None, um novo será gerado.
        """
        self.username = username
        self.profile_manager = profile_manager
        self.logging_settings = logging_settings
        self.snapshot_settings = snapshot_settings

        # Se um ID de sessão for fornecido, use-o. Caso contrário, gere um novo.
        self.session_id = session_id or generate_session_id(self.username)

        self.session_dir = self.profile_manager.create_session_directory(self.session_id)

        # A estrutura de pastas da sessão, incluindo logs, é criada aqui.
        self.paths: SessionPathConfig = self._create_session_structure()

        # O logger é configurado para guardar os ficheiros no diretório de logs da sessão.
        self.logger = setup_session_logger(
            session_id=self.session_id,
            username=self.username,
            logs_dir=self.paths["logs_dir"],
            config=self.logging_settings,
        )

        self._session_data: SessionData = {
            "session_id": self.session_id,
            "username": username,
            "profile_id": self.profile_manager.profile_id,
            "start_time": datetime.now().isoformat(),
            "status": "initialized",
            "snapshots": [],
        }
        self._lock = threading.RLock()
        self.logger.info(f"Gestor de sessão inicializado: {self.session_id}")

    def _create_session_structure(self) -> SessionPathConfig:
        # Cria a estrutura de subdiretórios dentro da pasta principal da sessão.
        paths: SessionPathConfig = {
            "session_dir": self.session_dir,
            "logs_dir": self.session_dir / "logs",
            "snapshots_dir": self.session_dir / "snapshots",
            "screenshots_dir": self.session_dir / "snapshots" / "screenshots",
            "browser_profile_dir": self.profile_manager.get_browser_profile_path(),
        }
        ensure_directory(paths["logs_dir"])
        ensure_directory(paths["snapshots_dir"])
        ensure_directory(paths["screenshots_dir"])
        return paths

    def start_session(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Marca o início oficial da sessão e guarda os metadados."""
        with self._lock:
            self._session_data["status"] = "active"
            if metadata:
                self._session_data["metadata"] = metadata
            self._save_session_data()
        self.logger.info("Sessão iniciada.")

    def end_session(self, status: str = "completed") -> None:
        """Marca o fim da sessão e atualiza o seu estado final."""
        with self._lock:
            self._session_data["status"] = status
            self._session_data["end_time"] = datetime.now().isoformat()
            self._save_session_data()
        self.logger.info(f"Sessão finalizada com estado: {status}")

    def take_snapshot(
            self,
            driver: WebDriverProtocol,
            name: str,
    ) -> Path:
        """
        Captura um 'snapshot' do estado atual do navegador.
        """
        if not self.snapshot_settings.get("enabled", True):
            return Path()

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            snapshot_name = f"{timestamp}_{name}"
            snapshot_dir = self.paths["snapshots_dir"] / snapshot_name
            ensure_directory(snapshot_dir)

            snapshot_data: SnapshotData = {
                "name": name,
                "timestamp": datetime.now().isoformat(),
                "url": driver.current_url,
            }

            if self.snapshot_settings.get("include_screenshot", True):
                screenshot_path = self.paths["screenshots_dir"] / f"{snapshot_name}.png"
                driver.save_screenshot(str(screenshot_path))
                snapshot_data["screenshot_path"] = str(screenshot_path)

            snapshot_file = snapshot_dir / "snapshot_data.json"
            with open(snapshot_file, "w", encoding="utf-8") as f:
                f.write(safe_json_dumps(snapshot_data, indent=2))

            with self._lock:
                self._session_data["snapshots"].append(snapshot_data)
                self._save_session_data()

            self.logger.info(f"Snapshot '{name}' capturado com sucesso.")
            return snapshot_dir

        except Exception as e:
            self.logger.error(f"Falha ao capturar o snapshot '{name}': {e}", exc_info=True)
            raise SnapshotError(f"Falha ao capturar o snapshot '{name}'", original_error=e)

    def _save_session_data(self) -> None:
        # Salva os metadados da sessão no ficheiro JSON.
        session_file = self.session_dir / "session_metadata.json"
        try:
            with self._lock:
                json_data = safe_json_dumps(self._session_data, indent=2)
                with open(session_file, "w", encoding="utf-8") as f:
                    f.write(json_data)
        except Exception as e:
            self.logger.error(f"Falha crítica ao salvar dados da sessão: {e}", exc_info=True)
