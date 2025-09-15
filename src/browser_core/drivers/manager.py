from pathlib import Path
from typing import Optional, Callable, Dict, Any, Type, cast, Tuple

from selenium.webdriver.remote.webdriver import WebDriver
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
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

        self._driver_map: Dict[str, Dict[str, Any]] = {
            BrowserType.CHROME.value: {
                "manager_cls": ChromeDriverManager,
                "service_cls": ChromeService,
                "options_cls": ChromeOptions,
                "webdriver_cls": webdriver.Chrome,
                "options_applier": self._apply_chrome_options,
            },
            BrowserType.FIREFOX.value: {
                "manager_cls": GeckoDriverManager,
                "service_cls": FirefoxService,
                "options_cls": FirefoxOptions,
                "webdriver_cls": webdriver.Firefox,
                "options_applier": self._apply_firefox_options,
            },
        }

    @staticmethod
    def _get_driver_manager_instance(
        manager_cls: Type[WDMBaseManager],
        browser_name: str,
        version: Optional[str],
        cache: Optional[DriverCacheManager],
    ) -> WDMBaseManager:
        """Cria uma instância do manager de driver apropriado com os argumentos corretos."""
        if browser_name == BrowserType.CHROME.value:
            driver_version_arg = (
                version if version and version.lower() != "latest" else None
            )
            chrome_manager_cls = cast(Type[ChromeDriverManager], manager_cls)
            return chrome_manager_cls(
                driver_version=driver_version_arg, cache_manager=cache
            )

        # O GeckoDriverManager não aceita o argumento 'driver_version'.
        return manager_cls(cache_manager=cache)

    def prewarm_driver(self, driver_info: DriverInfo) -> None:
        """Garante que o driver especificado esteja baixado no cache."""
        browser_name = driver_info.get("name", "").lower()
        requested_version = driver_info.get("version")

        mapping = self._driver_map.get(browser_name)
        if not mapping:
            raise ConfigurationError(f"Tipo de navegador não suportado: {browser_name}")

        cache = (
            DriverCacheManager(root_dir=str(self.driver_cache_dir))
            if self.driver_cache_dir
            else None
        )

        manager_cls: Type[WDMBaseManager] = mapping["manager_cls"]
        # A chamada usa o método estático.
        manager = self._get_driver_manager_instance(
            manager_cls, browser_name, requested_version, cache
        )

        try:
            manager.install()
        except Exception as e:
            self.logger.error(
                f"Falha ao pré-aquecer driver para {browser_name}: {e}", exc_info=True
            )
            raise DriverError(
                f"Falha ao pré-aquecer driver para {browser_name}",
                original_error=e,
            )

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
    ) -> Tuple[WebDriver, int]:
        """
        Cria e retorna uma instância de WebDriver e o PID do seu processo.
        """
        browser_name = driver_info.get("name", "").lower()
        requested_version = driver_info.get("version")
        self.logger.info(
            f"A criar driver para o navegador: {browser_name}, versão solicitada: {requested_version}"
        )

        mapping = self._driver_map.get(browser_name)
        if not mapping:
            raise ConfigurationError(f"Tipo de navegador não suportado: {browser_name}")

        options = mapping["options_cls"]()
        applier: Callable = mapping["options_applier"]
        applier(options, browser_config, user_profile_dir, driver_info)

        cache = (
            DriverCacheManager(root_dir=str(self.driver_cache_dir))
            if self.driver_cache_dir
            else None
        )

        manager_cls: Type[WDMBaseManager] = mapping["manager_cls"]
        # A chamada usa o método estático.
        manager = self._get_driver_manager_instance(
            manager_cls, browser_name, requested_version, cache
        )

        try:
            driver_path = manager.install()
            installed_driver_version = self._get_driver_version(manager)
            self.logger.info(
                f"A iniciar {browser_name.title()}Driver v{installed_driver_version} a partir de: {driver_path}"
            )
            service_cls: Type = mapping["service_cls"]
            webdriver_cls: Type = mapping["webdriver_cls"]
            service = service_cls(executable_path=driver_path)
            driver = webdriver_cls(service=service, options=options)

            # Captura o PID do processo do serviço do driver
            driver_pid = driver.service.process.pid
            self.logger.info(
                f"Driver iniciado com sucesso. PID do processo: {driver_pid}"
            )
            return driver, driver_pid
        except Exception as e:
            self.logger.error(
                f"Erro inesperado ao criar o driver para {browser_name}: {e}",
                exc_info=True,
            )
            raise DriverError(
                f"Erro inesperado ao criar o driver para {browser_name}",
                original_error=e,
            )

    def _get_driver_version(self, manager: WDMBaseManager) -> str:
        """Obtém a versão do driver a partir da instância do manager."""
        try:
            # Abordagem 1: Tenta obter através do método oficial, se existir
            if hasattr(manager, "get_driver_version"):
                return manager.get_driver_version()

            # Abordagem 2 (fallback): Tenta acessar o driver e sua versão interna
            driver_obj: Any = getattr(manager, "driver", None)
            if driver_obj and hasattr(driver_obj, "get_version"):
                return driver_obj.get_version()

            # Abordagem 3 (fallback para versões mais antigas do webdriver-manager):
            if hasattr(manager, "driver_cache"):
                # O método get_version_from_last_run pode existir em algumas versões
                if hasattr(manager.driver_cache, "get_version_from_last_run"):
                    return manager.driver_cache.get_version_from_last_run()

        except Exception as e:
            self.logger.warning(
                f"Erro inesperado ao obter a versão do driver dinamicamente: {e}",
                exc_info=True,
            )

        self.logger.warning(
            "Não foi possível obter a versão do driver dinamicamente. Retornando 'desconhecida'."
        )
        return "desconhecida"

    def _apply_chrome_options(
        self, options: ChromeOptions, config: BrowserConfig, profile_dir: FilePath, driver_info: Optional[DriverInfo] = None
    ) -> None:
        """Centraliza a aplicação de todas as opções de configuração do Chrome."""
        # Enhanced anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-breakpad")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-web-resources")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-permissions-api")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-sync-preferences")
        
        # Additional stealth arguments for enhanced anti-detection
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-breakpad")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-web-resources")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-permissions-api")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-sync-preferences")
        
        # Enhanced stealth options
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Additional stealth measures
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
            },
            "profile.managed_default_content_settings": {
                "images": 2
            },
            "profile.default_content_settings": {
                "popups": 0
            }
        }
        options.add_experimental_option("prefs", prefs)
        
        # Enhanced request header spoofing
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-breakpad")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-web-resources")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-permissions-api")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-sync-preferences")

        # Enhanced Proxy Support with Rotation
        proxy_url = config.get("proxy")
        proxy_rotation = config.get("proxy_rotation", False)
        proxy_list = config.get("proxy_list", [])
        
        if proxy_rotation and proxy_list:
            import random
            proxy_url = random.choice(proxy_list)
            self.logger.info(f"A usar proxy rotativo selecionado: {proxy_url}")
        elif proxy_url:
            self.logger.info(f"A usar proxy definido em configuração: {proxy_url}")
        
        if proxy_url:
            options.add_argument(f"--proxy-server={proxy_url}")
            options.add_argument("--proxy-bypass-list=<-loopback>")
            # Additional proxy settings for better stealth
            options.add_argument("--proxy-pac-url=")
            options.add_argument("--disable-proxy-certificate-handler")

        # Random User-Agent
        if config.get("random_user_agent") and not config.get("user_agent"):
            try:
                import random

                # Get browser version from driver info if available
                browser_version = driver_info.get("version", "120.0.0.0") if driver_info else "120.0.0.0"
                browser_name = driver_info.get("name", "chrome").lower() if driver_info else "chrome"

                if browser_name == "chrome":
                    # Generate Chrome user agents with actual version
                    chrome_versions = [browser_version, "119.0.0.0", "118.0.0.0"]
                    selected_version = random.choice(chrome_versions)
                    candidate_uas = [
                        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{selected_version} Safari/537.36",
                        f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{selected_version} Safari/537.36",
                        f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{selected_version} Safari/537.36",
                    ]
                elif browser_name == "firefox":
                    # Generate Firefox user agents
                    firefox_versions = ["121.0", "120.0", "119.0"]
                    selected_version = random.choice(firefox_versions)
                    candidate_uas = [
                        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{selected_version}) Gecko/20100101 Firefox/{selected_version}",
                        f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{selected_version}) Gecko/20100101 Firefox/{selected_version}",
                        f"Mozilla/5.0 (X11; Linux x86_64; rv:{selected_version}) Gecko/20100101 Firefox/{selected_version}",
                    ]
                else:
                    # Fallback to Chrome with snapshot version
                    candidate_uas = [
                        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Safari/537.36",
                    ]

                config["user_agent"] = random.choice(candidate_uas)
                self.logger.info(
                    f"User-Agent aleatório selecionado: {config['user_agent']}"
                )
            except Exception as e:
                self.logger.warning(f"Falha ao gerar User-Agent aleatório: {e}")
                pass

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

        if config.get("incognito"):
            self.logger.warning(
                "O modo 'incognito' está ativo. O perfil de usuário do snapshot será ignorado nesta execução."
            )
            options.add_argument("--incognito")
        else:
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

    @staticmethod
    def _setup_common_options(options: Any) -> None:
        if hasattr(options, "add_argument"):
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")

    def _apply_firefox_options(
        self, options: FirefoxOptions, config: BrowserConfig, profile_dir: FilePath, driver_info: Optional[DriverInfo] = None
    ) -> None:
        self._setup_common_options(options)
        if config.get("headless", True):
            options.add_argument("-headless")
        if not config.get("incognito"):
            options.set_preference("profile", str(profile_dir))
