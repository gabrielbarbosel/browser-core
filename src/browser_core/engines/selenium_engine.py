from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from selenium.common.exceptions import WebDriverException

from ..drivers.manager import DriverManager
from ..exceptions import PageLoadError, WorkerError
from ..selectors.manager import SelectorDefinition
from ..types import WebDriverProtocol
from ..windows.manager import WindowManager


class SeleniumEngine:
    """Implementação do AutomationEngine utilizando Selenium."""

    def __init__(self, worker: "Worker", config: dict) -> None:
        self._worker = worker
        self._config = config
        self._driver_manager = DriverManager(
            logger=worker.logger, settings=worker.settings
        )
        self._driver: Optional[WebDriverProtocol] = None
        self._window_manager: Optional[WindowManager] = None

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

    def start(self, profile_dir: Path) -> WebDriverProtocol:
        """Cria e configura o WebDriver baseado nas definições do worker."""
        self._driver = self._driver_manager.create_driver(
            driver_info=self._worker.driver_info,
            browser_config=self._worker.settings.get("browser", {}),
            user_profile_dir=profile_dir,
        )
        self._window_manager = WindowManager(self._worker)
        self._configure_driver_timeouts()
        return self._driver

    def stop(self) -> None:
        """Encerra o WebDriver e limpa referências internas."""
        if not self._driver:
            return
        try:
            self._driver.quit()
        except Exception as e:
            self._worker.logger.warning(f"Erro ao finalizar WebDriver: {e}")
        finally:
            self._driver = None
            self._window_manager = None

    def navigate_to(self, url: str) -> None:
        """Navega para a URL indicada utilizando o driver ativo."""
        if not self._driver:
            raise WorkerError("Driver não iniciado")
        try:
            self._driver.get(url)
        except WebDriverException as e:
            timeout_ms = self._worker.settings.get("timeouts", {}).get(
                "page_load_ms", 45_000
            )
            raise PageLoadError(
                f"Falha ao carregar a URL: {url}",
                context={"url": url, "timeout_ms": timeout_ms},
                original_error=e,
            )

    def find_element(self, selector: SelectorDefinition) -> Any:
        """Busca um elemento através do gerenciador de seletores do worker."""
        return self._worker.selector_manager.find_element(self.driver, selector)[0]

    def execute_script(self, script: str, *args: Any) -> Any:
        """Executa JavaScript diretamente no driver Selenium."""
        return self.driver.execute_script(script, *args)

    def _configure_driver_timeouts(self) -> None:
        """Aplica as configurações de timeout definidas nas settings."""
        if not self._driver:
            return
        timeouts = self._worker.settings.get("timeouts", {})
        page_load_sec = timeouts.get("page_load_ms", 45_000) / 1_000.0
        script_sec = timeouts.get("script_ms", 30_000) / 1_000.0
        self._driver.set_page_load_timeout(page_load_sec)
        self._driver.set_script_timeout(script_sec)
