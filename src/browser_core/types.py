# Define todos os tipos de dados, Enums e Protocolos para o browser-core.
#
# Este arquivo centraliza as estruturas de dados, garantindo consistência
# e permitindo a verificação estática de tipos no módulo. É um
# componente chave para um código robusto e de fácil manutenção.

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union
from typing_extensions import TypedDict

# ==============================================================================
# --- Tipos Primitivos e Aliases ---
# ==============================================================================

TimeoutMs = int
"""Representa um valor de tempo em milissegundos."""

FilePath = Union[str, Path]
"""Representa um caminho de arquivo, que pode ser uma string ou um objeto Path."""

SelectorValue = str
"""Representa o valor de um seletor de elemento da web (ex: '//div[@id="main"]')."""

ElementIndex = int
"""Representa o índice de um elemento em uma lista de elementos."""


# ==============================================================================
# --- Enums para Valores Controlados ---
# ==============================================================================

class BrowserType(Enum):
    """Define os tipos de navegadores suportados pela automação."""
    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"
    SAFARI = "safari"


class SelectorType(Enum):
    """Define os tipos de seletores de elementos da web suportados."""
    XPATH = "xpath"
    CSS = "css"
    ID = "id"
    NAME = "name"
    CLASS_NAME = "class_name"
    TAG_NAME = "tag_name"
    LINK_TEXT = "link_text"
    PARTIAL_LINK_TEXT = "partial_link_text"


class LogLevel(Enum):
    """Define os níveis de log padrão."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ==============================================================================
# --- Dicionários de Configuração (TypedDicts) ---
# ==============================================================================

class BrowserConfig(TypedDict, total=False):
    """Define a estrutura para as configurações do navegador."""
    headless: bool
    window_width: int
    window_height: int
    user_agent: Optional[str]
    incognito: bool
    disable_gpu: bool
    additional_args: List[str]


class TimeoutConfig(TypedDict, total=False):
    """Define a estrutura para as configurações de timeout (em ms)."""
    element_find_ms: TimeoutMs
    page_load_ms: TimeoutMs
    script_ms: TimeoutMs


class LoggingConfig(TypedDict, total=False):
    """Define a estrutura para as configurações de logging."""
    level: str
    to_file: bool
    to_console: bool
    format_type: str
    mask_credentials: bool


class SnapshotConfig(TypedDict, total=False):
    """Define a estrutura para as configurações de snapshots."""
    enabled: bool
    on_error: bool
    include_screenshot: bool
    include_dom: bool
    include_browser_logs: bool


class ProfileConfig(TypedDict, total=False):
    """Define a estrutura para as configurações de perfis de usuário."""
    auto_cleanup_days: int
    persistent_browser_profile: bool


class PathsConfig(TypedDict, total=False):
    """
    Define a estrutura para os caminhos de saída personalizáveis.
    Permite separar perfis, sessões e outros artefatos.
    """
    profiles_base_dir: FilePath
    sessions_base_dir: FilePath
    # Permite injetar um caminho de perfil ou sessão específico
    profile_path: FilePath
    session_path: FilePath
    session_id: str


class SessionPathConfig(TypedDict):
    """Define a estrutura de diretórios para uma sessão individual."""
    session_dir: Path
    logs_dir: Path
    snapshots_dir: Path
    screenshots_dir: Path
    browser_profile_dir: Optional[Path]


class ProfilePathConfig(TypedDict):
    """Define a estrutura de diretórios para um perfil de usuário."""
    profile_dir: Path
    sessions_dir: Path


# ==============================================================================
# --- Estruturas de Dados (TypedDicts) ---
# ==============================================================================

class SnapshotData(TypedDict, total=False):
    """Define a estrutura de dados para um snapshot."""
    name: str
    timestamp: str
    url: str
    screenshot_path: Optional[str]
    dom_path: Optional[str]
    browser_logs: List[Dict[str, Any]]


class SessionData(TypedDict, total=False):
    """Define a estrutura de dados principal para uma sessão."""
    session_id: str
    username: str
    profile_id: str
    start_time: str
    end_time: Optional[str]
    status: str
    snapshots: List[SnapshotData]
    metadata: Dict[str, Any]


class ProfileData(TypedDict, total=False):
    """Define a estrutura de dados para os metadados de um perfil."""
    profile_id: str
    username: str
    created_at: str
    last_accessed: str


# ==============================================================================
# --- Protocolos para Inversão de Dependência (SOLID) ---
# ==============================================================================

class UserProfileProtocol(Protocol):
    """Define o contrato para um gestor de perfis de utilizador."""

    @property
    def profile_id(self) -> str: ...

    def create_session_directory(self, session_id: str) -> Path: ...

    def get_browser_profile_path(self) -> Optional[Path]: ...


class WebDriverProtocol(Protocol):
    """Define o contrato mínimo que um objeto de WebDriver deve seguir."""

    @property
    def current_url(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def page_source(self) -> str: ...

    def get(self, url: str) -> None: ...

    def quit(self) -> None: ...

    def find_element(self, by: str, value: str) -> Any: ...

    def find_elements(self, by: str, value: str) -> List[Any]: ...

    def execute_script(self, script: str, *args: Any) -> Any: ...

    def save_screenshot(self, filename: str) -> bool: ...

    def get_cookies(self) -> List[Dict[str, Any]]: ...

    def get_log(self, log_type: str) -> Any: ...

    def set_page_load_timeout(self, time_to_wait: float) -> None: ...

    def set_script_timeout(self, time_to_wait: float) -> None: ...


class LoggerProtocol(Protocol):
    """Define o contrato para um objeto de logger compatível."""

    def debug(self, msg: object, *args: object, **kwargs: Any) -> None: ...

    def info(self, msg: object, *args: object, **kwargs: Any) -> None: ...

    def warning(self, msg: object, *args: object, **kwargs: Any) -> None: ...

    def error(self, msg: object, *args: object, **kwargs: Any) -> None: ...

    def critical(self, msg: object, *args: object, **kwargs: Any) -> None: ...
