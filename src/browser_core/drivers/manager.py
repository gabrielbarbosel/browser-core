# Este módulo fornece a classe 'DriverManager', que lida com o download
# automático, versionamento explícito (incluindo 'latest'), cache e
# configuração de WebDrivers, desacoplando o resto do framework dos
# detalhes de implementação de cada driver.

from pathlib import Path
from typing import Optional, Callable, Dict, Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager
from webdriver_manager.core.manager import DriverManager as WDMBaseManager

from ..exceptions import DriverError, ConfigurationError
from ..settings import Settings
from ..types import (
    BrowserConfig,
    DriverInfo,
    FilePath,
    LoggerProtocol,
    BrowserType,
    WebDriverProtocol,
)


class DriverManager:
    """
    Gere o ciclo de vida de instâncias de WebDriver com versionamento explícito.

    Abstrai a complexidade de obter o executável do driver correto, gere um
    cache global e configura as opções de inicialização de forma inteligente.
    """

    def __init__(
            self,
            logger: LoggerProtocol,
            settings: Settings,
    ):
        """
        Inicializa o gestor de drivers.
        """
        self.logger = logger
        self.settings = settings
        self.driver_cache_dir: Optional[Path] = None

        driver_cache_path_str = self.settings.get("paths", {}).get("driver_cache_dir")
        if driver_cache_path_str:
            self.driver_cache_dir = Path(driver_cache_path_str)
            self._ensure_cache_dir()
        else:
            self.logger.info(
                "Nenhum 'driver_cache_dir' fornecido. A usar o diretório de cache padrão do sistema."
            )

        self._driver_factories: Dict[str, Callable] = {
            BrowserType.CHROME.value: self._create_chrome_driver,
            # Futuramente, outros drivers podem ser adicionados aqui:
            # BrowserType.FIREFOX.value: self._create_firefox_driver,
        }

    def _ensure_cache_dir(self) -> None:
        """Garante que o diretório de cache para os drivers exista."""
        if not self.driver_cache_dir:
            return
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
            self.logger.error(
                f"Erro inesperado ao criar o driver para {browser_name}: {e}",
                exc_info=True,
            )
            raise DriverError(
                f"Erro inesperado ao criar o driver para {browser_name}",
                original_error=e,
            )

    def _create_chrome_driver(
            self,
            requested_version: str,
            config: BrowserConfig,
            profile_dir: FilePath,
    ) -> webdriver.Chrome:
        """Cria uma instância do ChromeDriver e retorna o objeto do driver."""
        options = ChromeOptions()
        self._apply_common_chrome_options(options, config, profile_dir)

        cache = (
            DriverCacheManager(root_dir=str(self.driver_cache_dir))
            if self.driver_cache_dir
            else None
        )

        driver_version_arg = (
            requested_version
            if requested_version and requested_version.lower() != "latest"
            else None
        )

        # O construtor do ChromeDriverManager recebe o 'cache_manager'
        manager = ChromeDriverManager(
            driver_version=driver_version_arg, cache_manager=cache
        )

        driver_path = manager.install()

        installed_driver_version = self._get_driver_version(manager)
        self.logger.info(
            f"A iniciar ChromeDriver v{installed_driver_version} a partir de: {driver_path}"
        )

        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)

        return driver

    def _get_driver_version(self, manager: WDMBaseManager) -> str:
        """Obtém a versão do driver a partir da instância do manager."""
        try:
            driver_obj: Any = getattr(manager, "driver", None)
            if driver_obj and hasattr(driver_obj, "get_version"):
                return driver_obj.get_version()
        except AttributeError:
            self.logger.debug("Atributo 'driver' ou 'get_version' não está disponível.")
        except Exception as e:
            self.logger.warning(
                f"Erro inesperado ao obter a versão do driver: {e}",
                exc_info=True,
            )

        self.logger.warning("Não foi possível obter a versão do driver dinamicamente.")
        return "desconhecida"

    def _apply_common_chrome_options(
            self, options: ChromeOptions, config: BrowserConfig, profile_dir: FilePath
    ) -> None:
        """Centraliza a aplicação de todas as opções de configuração do Chrome."""
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if config.get("user_agent"):
            self.logger.debug(
                f"A usar User-Agent fornecido na configuração: {config['user_agent']}"
            )
            options.add_argument(f"--user-agent={config['user_agent']}")
        else:
            self.logger.debug(
                "Nenhum User-Agent customizado fornecido. O padrão do WebDriver será usado."
            )

        if config.get("headless", True):
            options.add_argument("--headless=new")

        # Lógica para lidar com o modo anônimo ('incognito').
        # Se ativado, o perfil de usuário do snapshot é ignorado, pois são mutuamente exclusivos.
        if config.get("incognito"):
            self.logger.warning(
                "O modo 'incognito' está ativo. O perfil de usuário do snapshot será ignorado nesta execução."
            )
            options.add_argument("--incognito")
        else:
            # O perfil de usuário (essencial para snapshots) só é adicionado se não estiver em modo anônimo.
            options.add_argument(f"--user-data-dir={profile_dir}")

        if config.get("disable_gpu", True):
            options.add_argument("--disable-gpu")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        window_size = (
            f"{config.get('window_width', 1_920)},{config.get('window_height', 1_080)}"
        )
        options.add_argument(f"--window-size={window_size}")

        for arg in config.get("additional_args", []):
            options.add_argument(arg)
