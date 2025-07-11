from __future__ import annotations

from typing import Dict, Type, TYPE_CHECKING, Any

from .chrome import SeleniumChromeEngine
from .firefox import SeleniumFirefoxEngine
from ..base import AutomationEngine

if TYPE_CHECKING:  # pragma: no cover - usado apenas para type hints
    from ...orchestration.worker import Worker

ENGINE_CLASSES: Dict[str, Type[Any]] = {
    "chrome": SeleniumChromeEngine,
    "firefox": SeleniumFirefoxEngine,
}


class SeleniumProvider:
    """Fábrica de engines Selenium conforme o navegador."""

    def __init__(self, config: dict) -> None:
        self._config = config

    def get_engine(self, browser_name: str, worker: "Worker") -> AutomationEngine:
        engine_cls = ENGINE_CLASSES.get(browser_name.lower(), SeleniumChromeEngine)
        return engine_cls(worker, self._config)
