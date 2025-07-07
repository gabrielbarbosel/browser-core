# Define a API pública do pacote `browser_core`.
#
# Este arquivo atua como a fachada principal da biblioteca,
# tornando as classes, tipos e exceções mais importantes
# acessíveis de forma limpa e direta para o utilizador final.

# --- Classes Principais ---
from .browser import Browser
from .settings import Settings, default_settings
from .selectors.manager import SelectorDefinition, create_selector

# --- Tipos e Enums Essenciais ---
from .types import BrowserType, SelectorType

# --- Exceções Comuns ---
from .exceptions import (
    BrowserCoreError,
    BrowserManagementError,
    ConfigurationError,
    DriverError,
    ElementActionError,
    ElementNotFoundError,
    PageLoadError,
    ProfileError,
    SessionStateError,
    SnapshotError,
)

# A variável __all__ define a API pública explícita do pacote.
# Apenas os nomes listados aqui serão importados quando um cliente
# usar `from browser import *`.
__all__ = [
    # Classes principais
    "Browser",
    "Settings",
    "default_settings",
    "SelectorDefinition",
    "create_selector",

    # Enums importantes
    "BrowserType",
    "SelectorType",

    # Exceções
    "BrowserCoreError",
    "BrowserManagementError",
    "ElementNotFoundError",
    "ElementActionError",
    "PageLoadError",
    "SessionStateError",
    "SnapshotError",
    "DriverError",
    "ConfigurationError",
    "ProfileError",
]
