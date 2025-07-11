from __future__ import annotations

from pathlib import Path

from .base_engine import SeleniumBaseEngine
from ...drivers.manager import DriverManager
from ...types import WebDriverProtocol


class SeleniumChromeEngine(SeleniumBaseEngine):
    """Engine Selenium especializado para o Chrome."""

    def __init__(self, worker: "Worker", config: dict) -> None:
        super().__init__(worker, config)
        self._driver_manager = DriverManager(
            logger=worker.logger, settings=worker.settings
        )

    def _create_driver(self, profile_dir: Path) -> WebDriverProtocol:
        return self._driver_manager.create_driver(
            driver_info=self._worker.driver_info,
            browser_config=self._worker.settings.get("browser", {}),
            user_profile_dir=profile_dir,
        )

    def start(self, profile_dir: Path) -> WebDriverProtocol:
        driver = super().start(profile_dir)
        self._configure_driver_timeouts()
        return driver

    def _configure_driver_timeouts(self) -> None:
        """Aplica as configurações de timeout definidas nas settings."""
        if not self._driver:
            return
        timeouts = self._worker.settings.get("timeouts", {})
        page_load_sec = timeouts.get("page_load_ms", 45_000) / 1_000.0
        script_sec = timeouts.get("script_ms", 30_000) / 1_000.0
        self._driver.set_page_load_timeout(page_load_sec)
        self._driver.set_script_timeout(script_sec)
