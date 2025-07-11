from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from ...exceptions import PageLoadError, WorkerError
from ...types import WebDriverProtocol
from ...windows.manager import WindowManager

if TYPE_CHECKING:
    from ...orchestration.worker import Worker


class SeleniumBaseEngine(ABC):
    """Base para engines Selenium com lógica compartilhada."""

    def __init__(self, _worker: "Worker", _config: dict) -> None:
        super().__init__(_worker, _config)
        self._worker = _worker
        self._config = _config
        self._driver: Optional[WebDriverProtocol] = None
        self._window_manager: Optional[WindowManager] = None

    # --- Métodos que subclasses devem implementar ---
    @abstractmethod
    def _create_driver(self, profile_dir: Path) -> WebDriverProtocol:
        """Cria e retorna a instância específica de WebDriver."""

    @staticmethod
    def _setup_common_options(options: Any) -> None:
        """Aplica opções comuns de inicialização aos drivers."""
        if hasattr(options, "add_argument"):
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")

    # --- Implementação padrão do contrato AutomationEngine ---
    def start(self, profile_dir: Path) -> WebDriverProtocol:
        self._driver = self._create_driver(profile_dir)
        self._window_manager = WindowManager(self._worker)
        return self._driver

    def stop(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
            except Exception as e:  # pragma: no cover - log apenas
                self._worker.logger.warning(f"Erro ao finalizar WebDriver: {e}")
        self._driver = None
        self._window_manager = None

    def navigate_to(self, url: str) -> None:
        if not self._driver:
            raise WorkerError("Driver não iniciado")
        try:
            self._driver.get(url)
        except Exception as e:
            timeout_ms = self._worker.settings.get("timeouts", {}).get(
                "page_load_ms", 45_000
            )
            raise PageLoadError(
                f"Falha ao carregar a URL: {url}",
                context={"url": url, "timeout_ms": timeout_ms},
                original_error=e,
            )

    def find_element(self, selector: Any) -> Any:
        return self._worker.selector_manager.find_element(self.driver, selector)

    def execute_script(self, script: str, *args: Any) -> Any:
        return self.driver.execute_script(script, *args)

    @property
    def driver(self) -> WebDriverProtocol:
        if not self._driver:
            raise WorkerError("Driver não iniciado")
        return self._driver

    @property
    def window_manager(self) -> WindowManager:
        if not self._window_manager:
            raise WorkerError("Window manager não iniciado")
        return self._window_manager
