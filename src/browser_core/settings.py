# Define a estrutura de configuração unificada para o framework.
#
# Este módulo centraliza todas as configurações em um único objeto,
# simplificando a inicialização e o gerenciamento de parâmetros do sistema.

from pathlib import Path
from typing_extensions import TypedDict

# Importa as estruturas de configuração individuais do nosso arquivo de tipos.
from .types import (
    BrowserConfig,
    LoggingConfig,
    PathsConfig,
    TimeoutConfig,
)
from .utils import deep_merge_dicts


class Settings(TypedDict, total=False):
    """
    Estrutura de configuração principal e unificada para o Browser-Core.

    Agrupa todas as configurações num único objeto para facilitar
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
    disponíveis para personalização. Um módulo consumidor pode chamar
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


def custom_settings(overrides: Settings) -> Settings:
    """
    Cria uma configuração completa mesclando um objeto de substituição
    com as configurações padrão.

    Isto permite que o utilizador especifique apenas as configurações que
    deseja alterar, mantendo os padrões para o resto.

    Args:
        overrides: Um dicionário contendo apenas as chaves e valores
                   que se deseja modificar.

    Returns:
        Um objeto de configuração completo e pronto para ser usado.
    """
    base = default_settings()

    # Se o usuário sobrescrever 'output_dir', os caminhos derivados devem ser
    # recalculados com base no novo diretório, a menos que também tenham sido
    # definidos individualmente.
    custom_paths = overrides.get("paths", {})
    if "output_dir" in custom_paths:
        new_base = Path(custom_paths["output_dir"])
        # Se um caminho específico não foi sobrescrito, deriva ele do novo base.
        base["paths"]["objects_dir"] = custom_paths.get("objects_dir", new_base / "objects")
        base["paths"]["snapshots_metadata_dir"] = custom_paths.get("snapshots_metadata_dir", new_base / "snapshots")
        base["paths"]["tasks_logs_dir"] = custom_paths.get("tasks_logs_dir", new_base / "tasks_logs")
        base["paths"]["driver_cache_dir"] = custom_paths.get("driver_cache_dir", new_base / "drivers_cache")

    return deep_merge_dicts(base, overrides)
