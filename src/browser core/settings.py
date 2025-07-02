# Define a estrutura de configuração unificada para o framework.
#
# Este módulo centraliza todas as configurações em um único objeto,
# simplificando a inicialização e o gerenciamento de parâmetros do sistema.

from typing_extensions import TypedDict

# Importa as estruturas de configuração individuais do nosso arquivo de tipos.
# Isso garante que estamos a reutilizar os contratos já definidos.
from .types import (
    BrowserConfig,
    LoggingConfig,
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
        session_output_dir: O diretório raiz para todos os artefactos de sessão.
    """
    browser: BrowserConfig
    timeouts: TimeoutConfig
    logging: LoggingConfig
    profile: ProfileConfig
    snapshots: SnapshotConfig
    session_output_dir: str


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
            # Executa o navegador em modo "headless" (sem interface gráfica).
            # Ideal para ambientes de servidor e automação.
            "headless": True,
            # Largura da janela do navegador em pixels.
            "window_width": 1_920,
            # Altura da janela do navegador em pixels.
            "window_height": 1_080,
            # User-Agent personalizado para o navegador. Se 'None', usa o padrão.
            "user_agent": None,
            # Inicia o navegador em modo anónimo.
            "incognito": False,
            # Desativa a aceleração por GPU. Recomendado para estabilidade em servidores.
            "disable_gpu": True,
            # Argumentos de linha de comando adicionais para passar ao executável do navegador.
            "additional_args": [
                # Exemplo: "--disable-images" para carregar páginas mais rápido.
            ],
        },

        # --- Configurações de Timeout (em milissegundos) ---
        "timeouts": {
            # Tempo máximo para encontrar um elemento na página.
            "element_find_ms": 30_000,
            # Tempo máximo para o carregamento completo de uma página.
            "page_load_ms": 45_000,
            # Tempo máximo para a execução de um script JavaScript.
            "script_ms": 30_000,
        },

        # --- Configurações de Logging ---
        "logging": {
            # Nível mínimo de log a ser registado ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
            "level": "INFO",
            # Se 'True', guarda os logs num ficheiro dentro da pasta da sessão.
            "to_file": True,
            # Se 'True', exibe os logs na consola em tempo real.
            "to_console": True,
            # Formato do log ('detailed', 'json').
            "format_type": "detailed",
            # Se 'True', mascara automaticamente dados sensíveis como senhas e tokens nos logs.
            "mask_credentials": True,
        },

        # --- Configurações de Perfis de Utilizador ---
        "profile": {
            # Se 'True', o perfil do navegador (cookies, etc.) é guardado entre execuções.
            "persistent_browser_profile": True,
            # Número de dias para manter os diretórios de sessões antigas.
            # Use 0 para desativar a limpeza automática.
            "auto_cleanup_days": 0,
        },

        # --- Configurações de Snapshots ---
        "snapshots": {
            # Ativa ou desativa completamente a funcionalidade de snapshots.
            "enabled": True,
            # Se 'True', tira um snapshot automaticamente sempre que ocorre um erro não tratado.
            "on_error": True,
            # Se 'True', inclui um screenshot do ecrã no snapshot.
            "include_screenshot": True,
            # Se 'True', inclui uma cópia do DOM (código HTML) da página no snapshot.
            "include_dom": False,  # Desativado por padrão, pois pode gerar ficheiros grandes.
            # Se 'True', inclui os logs da consola do navegador no snapshot.
            "include_browser_logs": False,
        },

        # --- Diretório de Saída ---
        # O caminho para a pasta onde todos os perfis e sessões serão guardados.
        "session_output_dir": "./browser-core-output",
    }
    return settings
