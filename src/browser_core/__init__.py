# Define a API pública do pacote 'browser-core'.
#
# Este arquivo atua como a fachada principal da biblioteca,
# tornando os componentes da nova arquitetura de orquestração
# acessíveis de forma limpa e direta para o utilizador final.
# --- Classes de Orquestração e Execução ---
from .engines import (
    AutomationEngine,
    PlaywrightEngine,
    SeleniumProvider,
    SeleniumChromeEngine,
    SeleniumFirefoxEngine,
)
# --- Exceções Principais ---
from .exceptions import (
    BrowserCoreError,
    ConfigurationError,
    DriverError,
    ElementActionError,
    ElementNotFoundError,
    PageLoadError,
    SnapshotError,
    StorageEngineError,
    WorkerError,
)
from .orchestration import Orchestrator, Worker
# --- Funções de Conveniência ---
from .selectors import create_selector, SelectorDefinition
from .settings import Settings, default_settings
from .snapshots.manager import SnapshotManager
from .storage.engine import StorageEngine
# --- Tipos e Enums Essenciais ---
from .types import BrowserType, SelectorType, SnapshotId, DriverInfo, SnapshotData

# A variável __all__ define a API pública explícita do pacote.
# Apenas os nomes listados aqui serão importados quando um cliente
# usar 'from browser_core import *'.
__all__ = [
    # --- Classes Principais ---
    "Orchestrator",
    "SnapshotManager",
    "Worker",  # Expor o Worker é útil para type hinting nas funções de tarefa.
    "StorageEngine",  # Expor para cenários de uso avançado ou customização.
    "SeleniumProvider",
    "SeleniumChromeEngine",
    "SeleniumFirefoxEngine",
    "PlaywrightEngine",
    "AutomationEngine",
    # --- Configuração ---
    "Settings",
    "default_settings",
    # --- Seletores ---
    "create_selector",
    "SelectorDefinition",
    # --- Enums e Tipos de Dados Chave ---
    "BrowserType",
    "SelectorType",
    "SnapshotId",
    "DriverInfo",
    "SnapshotData",
    # --- Hierarquia de Exceções ---
    "BrowserCoreError",
    "ConfigurationError",
    "DriverError",
    "ElementActionError",
    "ElementNotFoundError",
    "PageLoadError",
    "SnapshotError",
    "StorageEngineError",
    "WorkerError",
]
