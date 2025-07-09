# Define o sistema de gestão de WebDrivers.
#
# Este módulo fornece a classe `DriverManager`, que lida com o download
# automático, versionamento explícito (incluindo 'latest'), cache e
# configuração de WebDrivers, desacoplando o resto do framework dos
# detalhes de implementação de cada driver.

import inspect
from pathlib import Path
from typing import Any, Optional, Callable, Dict

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from ..exceptions import DriverError, ConfigurationError
from ..types import BrowserConfig, DriverInfo, FilePath, LoggerProtocol, BrowserType, WebDriverProtocol


class DriverManager:
    """
    Gere o ciclo de vida de instâncias de WebDriver com versionamento explícito.

    Abstrai a complexidade de obter o executável do driver correto, gere um
    cache global e configura as opções de inicialização de forma inteligente.
    """

    def __init__(
            self,
            logger: LoggerProtocol,
            driver_cache_dir: Optional[FilePath] = None,
    ):
        """
        Inicializa o gestor de drivers.
        """
        self.logger = logger
        if driver_cache_dir:
            self.driver_cache_dir = Path(driver_cache_dir)
            self._ensure_cache_dir()
        else:
            self.driver_cache_dir = None
            self.logger.info("Nenhum 'driver_cache_dir' fornecido. A usar o diretório de cache padrão do sistema.")

        # Mapa de despacho para as funções de criação de driver (Padrão Factory)
        self._driver_factories: Dict[str, Callable] = {
            BrowserType.CHROME.value: self._create_chrome_driver,
            # Futuramente, outros drivers podem ser adicionados aqui:
            # BrowserType.FIREFOX.value: self._create_firefox_driver,
        }

    def _ensure_cache_dir(self) -> None:
        """Garante que o diretório de cache para os drivers exista."""
        try:
            self.driver_cache_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            self.logger.warning(
                f"Não foi possível criar ou aceder ao diretório de cache de drivers: {self.driver_cache_dir}. "
                f"A usar o diretório padrão do sistema. Erro: {e}"
            )
            self.driver_cache_dir = None

    def create_driver(
            self,
            driver_info: DriverInfo,
            browser_config: BrowserConfig,
            user_profile_dir: FilePath,
    ) -> WebDriverProtocol:
        """
        Cria e retorna uma instância de WebDriver com base no nome do navegador.
        """
        browser_name = driver_info.get("name", "").lower()
        requested_version = driver_info.get("version")
        self.logger.info(
            f"A criar driver para o navegador: {browser_name}, versão solicitada: {requested_version}"
        )

        factory = self._driver_factories.get(browser_name)
        if not factory:
            raise ConfigurationError(f"Tipo de navegador não suportado: {browser_name}")

        try:
            return factory(requested_version, browser_config, user_profile_dir)
        except Exception as e:
            self.logger.error(f"Erro inesperado ao criar o driver para {browser_name}: {e}", exc_info=True)
            raise DriverError(f"Erro inesperado ao criar o driver para {browser_name}", original_error=e)

    def _create_chrome_driver(
            self,
            requested_version: str,
            config: BrowserConfig,
            profile_dir: FilePath,
    ) -> webdriver.Chrome:
        """Cria uma instância do ChromeDriver e retorna o objeto do driver."""
        options = ChromeOptions()
        self._apply_common_chrome_options(options, config, profile_dir)

        kwargs_para_manager = {}
        if requested_version.lower() == "latest":
            self.logger.debug("A procurar a versão mais recente do ChromeDriver compatível...")
        else:
            self.logger.debug(f"A garantir que a versão {requested_version} do ChromeDriver esteja disponível...")
            init_params = inspect.signature(ChromeDriverManager).parameters
            possible_args = {"version": requested_version, "driver_version": requested_version}
            kwargs_para_manager = {key: value for key, value in possible_args.items() if key in init_params}

        if self.driver_cache_dir:
            kwargs_para_manager["path"] = str(self.driver_cache_dir)

        manager = ChromeDriverManager(**kwargs_para_manager)
        driver_path = manager.install()

        installed_driver_version = Path(driver_path).parent.name
        self.logger.info(f"A iniciar ChromeDriver v{installed_driver_version} a partir de: {driver_path}")

        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)

        return driver

    def _apply_common_chrome_options(
            self, options: ChromeOptions, config: BrowserConfig, profile_dir: FilePath
    ) -> None:
        """Centraliza a aplicação de todas as opções de configuração do Chrome."""
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if config.get("user_agent"):
            self.logger.debug(f"A usar User-Agent fornecido na configuração: {config['user_agent']}")
            options.add_argument(f"--user-agent={config['user_agent']}")
        else:
            self.logger.debug("Nenhum User-Agent customizado fornecido. O padrão do WebDriver será usado.")

        if config.get("headless", True):
            options.add_argument("--headless=new")
        if config.get("incognito"):
            self.logger.warning(
                "A opção 'incognito' está ativa, o perfil materializado pode não ser usado completamente.")
            options.add_argument("--incognito")
        if config.get("disable_gpu", True):
            options.add_argument("--disable-gpu")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--user-data-dir={profile_dir}")
        window_size = f"{config.get('window_width', 1920)},{config.get('window_height', 1080)}"
        options.add_argument(f"--window-size={window_size}")

        for arg in config.get("additional_args", []):
            options.add_argument(arg)
