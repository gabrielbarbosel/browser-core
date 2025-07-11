from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from ..selectors.manager import SelectorDefinition
    from ..orchestration.worker import Worker


class AutomationEngine(Protocol):
    """Contrato comum para motores de automação."""

    def __init__(self, _worker: "Worker", _config: dict) -> None: ...

    def start(self, profile_dir: Path): ...

    def stop(self) -> None: ...

    def navigate_to(self, url: str) -> None: ...

    def find_element(self, selector: "SelectorDefinition") -> Any: ...

    def execute_script(self, script: str, *args: Any) -> Any: ...
