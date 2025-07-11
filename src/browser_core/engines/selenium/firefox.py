from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.core.driver_cache import DriverCacheManager
from webdriver_manager.firefox import GeckoDriverManager

from .base_engine import SeleniumBaseEngine
from ...types import WebDriverProtocol

if TYPE_CHECKING:
    from ...orchestration.worker import Worker


class SeleniumFirefoxEngine(SeleniumBaseEngine):
    """Engine Selenium especializado para o Firefox."""

    def __init__(self, worker: "Worker", config: dict) -> None:
        super().__init__(worker, config)

    def _create_driver(self, profile_dir: Path) -> WebDriverProtocol:
        options = FirefoxOptions()
        self._setup_common_options(options)
        if self._config.get("headless", True):
            options.add_argument("-headless")
        if not self._config.get("incognito"):
            options.set_preference("profile", str(profile_dir))
        cache = (
            DriverCacheManager(
                root_dir=str(
                    self._worker.settings.get("paths", {}).get("driver_cache_dir")
                )
            )
            if self._worker.settings.get("paths", {}).get("driver_cache_dir")
            else None
        )
        manager = GeckoDriverManager(cache_manager=cache)
        driver_path = manager.install()
        service = FirefoxService(executable_path=driver_path)
        driver = cast(
            WebDriverProtocol, webdriver.Firefox(service=service, options=options)
        )
        return driver

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
