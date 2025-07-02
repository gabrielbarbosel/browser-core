# Define o sistema de gestão de WebDrivers.
#
# Este módulo fornece uma classe, `DriverManager`, que lida com o download
# automático, cache e configuração de WebDrivers para múltiplos navegadores,
# desacoplando o resto do framework dos detalhes de implementação de
# cada driver específico.

from pathlib import Path
from typing import Any, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from ..exceptions import BrowserManagementError, ConfigurationError
from ..types import BrowserConfig, BrowserType, FilePath, LoggerProtocol


class DriverManager:
    """
    Gere o ciclo de vida de instâncias de WebDriver.

    Abstrai a complexidade de obter o executável do driver correto,
    gere um cache global para economizar tempo e largura de banda, e
    configura as opções específicas de cada navegador.
    """

    def __init__(
            self,
            logger: LoggerProtocol,
            driver_cache_dir: Optional[FilePath] = None,
    ):
        """
        Inicializa o gestor de drivers.

        Args:
            logger: A instância do logger para registar as operações.
            driver_cache_dir: O diretório para armazenar em cache os drivers.
                              Se não for fornecido, um diretório padrão será usado.
        """
        self.logger = logger
        # Define o diretório de cache padrão para o nosso projeto.
        if driver_cache_dir:
            self.driver_cache_dir = Path(driver_cache_dir)
        else:
            self.driver_cache_dir = Path.home() / ".browser-core" / "drivers"

        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        # Garante que o diretório de cache para os drivers exista.
        try:
            self.driver_cache_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            self.logger.warning(
                f"Não foi possível criar ou aceder ao diretório de cache de drivers: {self.driver_cache_dir}. "
                f"A usar o diretório temporário do sistema. Erro: {e}"
            )
            # Como fallback, não define um caminho, deixando o webdriver-manager usar o seu padrão.
            self.driver_cache_dir = None

    def create_driver(
            self,
            browser_type: BrowserType,
            browser_config: BrowserConfig,
            user_profile_dir: Optional[FilePath] = None,
    ) -> Any:
        """
        Cria e retorna uma instância de WebDriver configurada.

        Este método determina qual navegador criar, configura as suas opções
        específicas (como modo headless e perfil de utilizador) e gere
        o download e cache do driver correspondente.

        Args:
            browser_type: O tipo de navegador a ser criado (ex: BrowserType.CHROME).
            browser_config: O dicionário de configuração para o navegador.
            user_profile_dir: O caminho para o diretório de perfil de utilizador a ser usado.

        Returns:
            Uma instância do WebDriver iniciada e configurada.
        """
        self.logger.info(f"A criar driver para o navegador: {browser_type.value}")
        try:
            if browser_type == BrowserType.CHROME:
                return self._create_chrome_driver(browser_config, user_profile_dir)
            elif browser_type == BrowserType.FIREFOX:
                return self._create_firefox_driver(browser_config, user_profile_dir)
            else:
                raise ConfigurationError(f"Tipo de navegador não suportado: {browser_type.value}")
        except Exception as e:
            self.logger.error(f"Falha ao criar o driver para {browser_type.value}: {e}", exc_info=True)
            raise BrowserManagementError(
                f"Falha ao criar o driver para {browser_type.value}", original_error=e
            )

    def _create_chrome_driver(
            self,
            config: BrowserConfig,
            profile_dir: Optional[FilePath],
    ) -> webdriver.Chrome:
        # Cria uma instância específica do ChromeDriver.
        options = ChromeOptions()
        self._apply_common_chrome_options(options, config, profile_dir)

        self.logger.debug("A verificar o driver para o Chrome (a usar cache se disponível)...")
        # O 'install()' do ChromeDriverManager gere o download e o cache automaticamente.
        driver_path = ChromeDriverManager(path=str(self.driver_cache_dir) if self.driver_cache_dir else None).install()

        service = ChromeService(executable_path=driver_path)
        self.logger.info(f"A iniciar ChromeDriver a partir de: {driver_path}")
        return webdriver.Chrome(service=service, options=options)

    def _apply_common_chrome_options(
            self, options: ChromeOptions, config: BrowserConfig, profile_dir: Optional[FilePath]
    ) -> None:
        # Centraliza a aplicação de todas as opções de configuração do Chrome.
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if config.get("headless", True):
            options.add_argument("--headless=new")
        if config.get("incognito"):
            options.add_argument("--incognito")
        if config.get("disable_gpu", True):
            options.add_argument("--disable-gpu")

        # Argumentos essenciais para execução em ambientes containerizados (Docker).
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # Configura o perfil de utilizador para persistência de sessão.
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")

        window_size = f"{config.get('window_width', 1920)},{config.get('window_height', 1080)}"
        options.add_argument(f"--window-size={window_size}")

        if config.get("user_agent"):
            options.add_argument(f"--user-agent={config['user_agent']}")

        for arg in config.get("additional_args", []):
            options.add_argument(arg)

    def _create_firefox_driver(
            self,
            config: BrowserConfig,
            profile_dir: Optional[FilePath],
    ) -> webdriver.Firefox:
        # Implementação para o GeckoDriver (Firefox), similar à do Chrome.
        raise NotImplementedError("A criação do driver para Firefox ainda não foi implementada.")
