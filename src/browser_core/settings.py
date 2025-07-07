# Define a estrutura de configuração unificada para o framework.
#
# Este módulo centraliza todas as configurações em um único objeto,
# simplificando a inicialização e o gerenciamento de parâmetros do sistema.

from typing_extensions import TypedDict

# Importa as estruturas de configuração individuais do nosso arquivo de tipos.
# Isso garante que estamos a reutilizar os contratos já definidos.
from .utils import deep_merge_dicts
from .types import (
    BrowserConfig,
    LoggingConfig,
    PathsConfig,
    ProfileConfig,
    SnapshotConfig,
    TimeoutConfig,
)


class Settings(TypedDict, total=False):
    """
    Estrutura de configuração principal e unificada para o Browser-Core.

    Agrupa todas as configurações num único objeto para facilitar
    a passagem de parâmetros e a extensibilidade futura.

    Attributes:
        browser: Configurações específicas do comportamento do navegador.
        timeouts: Configurações para tempos de espera (page load, scripts, etc.).
        logging: Configurações do sistema de logs.
        profile: Configurações de gestão de perfis de utilizador.
        snapshots: Configurações para a captura de snapshots.
        paths: Configurações para os caminhos de saída dos artefatos.
    """
    browser: BrowserConfig
    timeouts: TimeoutConfig
    logging: LoggingConfig
    profile: ProfileConfig
    snapshots: SnapshotConfig
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
            "format_type": "detailed",
            "mask_credentials": True,
        },

        # --- Configurações de Perfis de Utilizador ---
        "profile": {
            "persistent_browser_profile": True,
            "auto_cleanup_days": 0,
        },

        # --- Configurações de Snapshots ---
        "snapshots": {
            "enabled": True,
            "on_error": True,
            "include_screenshot": True,
            "include_dom": False,
            "include_browser_logs": False,
        },

        # --- Configurações de Caminhos de Saída ---
        "paths": {
            # Caminho base para todos os perfis de usuário.
            "profiles_base_dir": "./browser-core-output/profiles",

            # Caminho base para todas as sessões de automação.
            "sessions_base_dir": "./browser-core-output/sessions",

            # Permite injetar um ID de sessão customizado.
            # Se não for fornecido, um ID será gerado automaticamente.
            # Ex: "user_A:minha_tarefa_123"
            "session_id": None,
        },
    }
    return settings


def custom_settings(overrides: Settings) -> Settings:
    """
    Cria uma configuração completa mesclando um objeto de substituição
    com as configurações padrão.

    Isso permite especificar apenas as configurações que você deseja alterar,
    semelhante a uma operação de atualização em um banco de dados.

    Args:
        overrides: Um dicionário contendo apenas as chaves e valores
                   que você deseja modificar.

    Returns:
        Um objeto de configuração completo e pronto para ser usado.
    """
    base = default_settings()
    return deep_merge_dicts(base, overrides)
