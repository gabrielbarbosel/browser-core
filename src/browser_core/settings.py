# Define a estrutura de configuração unificada para o framework.
#
# Este módulo centraliza todas as configurações em um único objeto,
# simplificando a inicialização e o gerenciamento de parâmetros do sistema.

from pathlib import Path
from typing import cast, Any
from typing_extensions import TypedDict, Literal

# Importa as estruturas de configuração individuais do nosso arquivo de tipos.
from .types import (
    BrowserConfig,
    LoggingConfig,
    PathsConfig,
    TimeoutConfig,
    FilePath,
)
from .utils import deep_merge_dicts

DerivedPathKey = Literal[
    "objects_dir",
    "snapshots_metadata_dir",
    "tasks_logs_dir",
    "driver_cache_dir",
]


class Settings(TypedDict, total=False):
    """
    Estrutura de configuração principal e unificada para o Browser-Core.

    Agrupa todas as configurações em um único objeto para facilitar
    a passagem de parâmetros para o WorkforceManager e os Workers.

    Attributes:
        browser: Configurações específicas do comportamento do navegador.
        timeouts: Configurações para tempos de espera (page load, scripts, etc.).
        logging: Configurações do sistema de logs para as tarefas.
        paths: Configurações para os caminhos de saída dos artefatos.
    """

    browser: BrowserConfig
    timeouts: TimeoutConfig
    logging: LoggingConfig
    paths: PathsConfig


def default_settings() -> Settings:
    """
    Fornece um conjunto completo de configurações padrão.

    Esta função serve como documentação viva, mostrando todas as opções
    disponíveis para personalização. Um módulo cliente pode chamar
    esta função para obter uma base de configuração e então sobrescrever
    apenas o que for necessário.

    Returns:
        Um dicionário de Settings com valores padrão preenchidos.
    """
    # Define um diretório de saída base para todos os artefatos gerados.
    base_output_path = Path("./browser-core-output")

    settings: Settings = {
        # --- Configurações do Navegador ---
        "browser": {
            "headless": True,
            "window_width": 1_920,
            "window_height": 1_080,
            "user_agent": None,
            "incognito": False,
            "disable_gpu": True,
            "additional_args": [],
        },
        # --- Configurações de Timeout (em milissegundos) ---
        "timeouts": {
            "element_find_ms": 30_000,
            "page_load_ms": 45_000,
            "script_ms": 30_000,
            # Timeout para operações de gestão de janelas, como esperar uma nova aba abrir.
            "window_management_ms": 10_000,
        },
        # --- Configurações de Logging ---
        "logging": {
            "level": "INFO",
            "to_file": True,
            "to_console": True,
            "format_type": "detailed",  # Pode ser 'detailed' ou 'json'
            "mask_credentials": True,
        },
        # --- Configurações de Caminhos de Saída ---
        # Por padrão, todos os caminhos são derivados do 'output_dir'.
        # O usuário pode sobrescrever 'output_dir' para mover tudo de uma vez,
        # ou sobrescrever um caminho específico (ex: 'tasks_logs_dir') individualmente.
        "paths": {
            "output_dir": base_output_path,
            "objects_dir": base_output_path / "objects",
            "snapshots_metadata_dir": base_output_path / "snapshots",
            "tasks_logs_dir": base_output_path / "tasks_logs",
            "driver_cache_dir": base_output_path / "drivers_cache",
        },
    }
    return settings


def custom_settings(overrides: dict[str, Any]) -> Settings:
    """
    Cria uma configuração completa mesclando um objeto de substituição
    com as configurações padrão.

    Isto permite que o usuário especifique apenas as configurações que
    deseja alterar, mantendo os padrões para o resto.

    Args:
        overrides: Um dicionário contendo apenas as chaves e valores
                   que se deseja modificar.

    Returns:
        Um objeto de configuração completo e pronto para ser usado.
    """
    base = default_settings()
    custom_paths = overrides.get("paths", {})

    # Se o usuário sobrescrever 'output_dir', os caminhos derivados devem ser
    # recalculados com base no novo diretório, a menos que também tenham sido
    # definidos individualmente na substituição.
    if "output_dir" in custom_paths:
        new_base_path = Path(cast(FilePath, custom_paths["output_dir"]))
        base_paths = base["paths"]
        base_paths["output_dir"] = new_base_path

        derived_paths_config: dict[DerivedPathKey, str] = {
            "objects_dir": "objects",
            "snapshots_metadata_dir": "snapshots",
            "tasks_logs_dir": "tasks_logs",
            "driver_cache_dir": "drivers_cache",
        }

        for key, suffix in derived_paths_config.items():
            if key not in custom_paths:
                base_paths[key] = new_base_path / suffix

    return cast(Settings, deep_merge_dicts(cast(dict[str, Any], base), cast(dict[str, Any], overrides)))
