# Define a classe principal de orquestração do navegador.
#
# A classe `Browser` integra todos os componentes do `browser_core`
# (gestores de sessão, perfil, driver, seletores) numa única
# interface coesa, simplificando as operações de automação.

import atexit
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

from selenium.common.exceptions import WebDriverException

from .drivers.manager import DriverManager
from .exceptions import BrowserManagementError, PageLoadError
from .profile import UserProfileManager
from .selectors.manager import SelectorDefinition, SelectorManager
from .session import SessionManager
from .settings import Settings, default_settings
from .types import BrowserType, WebDriverProtocol
from .utils import deep_merge_dicts
from .windows.manager import WindowManager
from .windows.tab import Tab


class Browser:
    """
    Orquestra todas as operações de automação do navegador.

    Esta classe atua como uma 'Facade', fornecendo uma API simplificada para
    interagir com o navegador, enquanto gere a complexidade da
    comunicação entre os diferentes gestores nos bastidores.
    """

    def __init__(
            self,
            username: str,
            browser_type: BrowserType,
            settings: Optional[Settings] = None,
    ):
        """
        Inicializa a instância do Browser.

        Args:
            username: Nome do utilizador para vincular à sessão e ao perfil.
            browser_type: O tipo de navegador a ser usado (ex: BrowserType.CHROME).
            settings: Um objeto de configuração unificado. Se não for fornecido,
                      serão usadas as configurações padrão.
        """
        base_settings = default_settings()
        self.settings = deep_merge_dicts(base_settings, settings) if settings else base_settings

        self.browser_type = browser_type
        self._driver: Optional[WebDriverProtocol] = None
        self._is_started = False

        profile_settings = self.settings.get("profile", {})
        paths_config = self.settings.get("paths", {})
        profiles_base_dir = Path(paths_config.get("profiles_base_dir", "./browser-core-output/profiles"))

        self.profile_manager = UserProfileManager(
            username=username,
            base_profiles_dir=profiles_base_dir,
            settings=profile_settings,
        )
        self.session_manager = SessionManager(
            username=username,
            profile_manager=self.profile_manager,
            logging_settings=self.settings.get("logging", {}),
            snapshot_settings=self.settings.get("snapshots", {}),
            session_id=self.settings.get("paths", {}).get("session_id", None),
        )
        self.driver_manager = DriverManager(logger=self.session_manager.logger)
        self.selector_manager = SelectorManager(logger=self.session_manager.logger)

        self.window_manager: Optional[WindowManager] = None
        self.logger = self.session_manager.logger
        self.logger.browser_instance = self # Fornece ao logger acesso ao estado do browser (ex: abas)
        atexit.register(self._cleanup)
        self.logger.info("Instância do Browser criada e pronta para iniciar.")

    def start(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Inicia a sessão de automação, o WebDriver e os gestores."""
        if self._is_started:
            self.logger.warning("O método start() foi chamado, mas o navegador já está iniciado.")
            return

        self.logger.info("Iniciando a sessão do navegador...")
        try:
            start_time = time.time()
            self.session_manager.start_session(metadata)

            self._driver = self.driver_manager.create_driver(
                browser_type=self.browser_type,
                browser_config=self.settings.get("browser", {}),
                user_profile_dir=self.profile_manager.get_browser_profile_path(),
            )

            # Inicializa o WindowManager, passando a si mesmo (self) como argumento
            self.window_manager = WindowManager(self)

            self._configure_driver_timeouts()
            self._is_started = True

            duration = (time.time() - start_time) * 1000
            self.logger.info(f"Navegador iniciado com sucesso em {duration:.2f}ms.")
        except Exception as e:
            self.logger.error(f"Falha crítica ao iniciar o navegador: {e}", exc_info=True)
            self._cleanup()
            raise BrowserManagementError(f"Falha ao iniciar a sessão do navegador: {e}", original_error=e)

    def stop(self, take_final_snapshot: bool = True) -> None:
        """Finaliza a sessão de automação de forma limpa."""
        if not self._is_started:
            return

        self.logger.info("Finalizando a sessão do navegador...")
        try:
            if take_final_snapshot and self._driver:
                self.take_snapshot("session_end")
        finally:
            if self._driver:
                try:
                    self._driver.quit()
                except Exception as e:
                    self.logger.warning(f"Erro ao finalizar o WebDriver: {e}")
                self._driver = None
            self.session_manager.end_session("completed")
            self._is_started = False
            self.logger.info("Sessão do navegador finalizada.")

    def navigate_to(self, url: str) -> None:
        """Navega para uma URL especificada."""
        self._ensure_started()
        self.logger.info(f"Navegando para a URL: {url}")
        try:
            self._driver.get(url)
        except WebDriverException as e:
            page_load_timeout = self.settings.get("timeouts", {}).get("page_load_ms", 45000)
            raise PageLoadError(f"Falha ao carregar a URL: {url}", url=url, timeout_ms=page_load_timeout,
                                original_error=e)

    def find_element(self, definition: SelectorDefinition) -> Any:
        """Delega a busca de um elemento para o SelectorManager."""
        self._ensure_started()
        return self.selector_manager.find_element(self._driver, definition)

    def take_snapshot(self, name: str) -> Path:
        """Delega a captura de um snapshot para o SessionManager."""
        self._ensure_started()
        return self.session_manager.take_snapshot(self._driver, name)

    def execute_script(self, script: str, *args: Any) -> Any:
        """Executa um script JavaScript no contexto da página atual."""
        self._ensure_started()
        return self._driver.execute_script(script, *args)

    def open_tab(self, name: Optional[str] = None) -> Tab:
        """
        Abre uma nova aba e retorna o objeto Tab controlador.
        """
        self._ensure_started()
        return self.window_manager.open_tab(name)

    def get_tab(self, name: str) -> Optional[Tab]:
        """Busca e retorna um objeto Tab pelo seu nome."""
        self._ensure_started()
        return self.window_manager.get_tab(name)

    def list_tab_names(self) -> List[str]:
        """Retorna uma lista com os nomes de todas as abas abertas."""
        self._ensure_started()
        return list(self.window_manager._tabs.keys())

    def get_all_tabs(self) -> List[Tab]:
        """Retorna a lista completa de objetos Tab controladores."""
        self._ensure_started()
        return list(self.window_manager._tabs.values())

    @property
    def current_tab(self) -> Optional[Tab]:
        """Retorna o objeto Tab da aba que está atualmente em foco."""
        self._ensure_started()
        current_handle = self._driver.current_window_handle
        for tab in self.get_all_tabs():
            if tab.handle == current_handle:
                return tab
        return None

    def switch_to_tab(self, name: str) -> None:
        """Alterna o foco para uma aba usando seu nome (string)."""
        self._ensure_started()
        self.window_manager.switch_to_tab(name)

    def close_tab(self, name: Optional[str] = None) -> None:
        """Fecha uma aba específica. Se nenhum nome for fornecido, fecha a aba atual."""
        self._ensure_started()
        self.window_manager.close_tab(name)

    # --- Métodos Internos ---

    def _ensure_started(self) -> None:
        if not self._is_started or not self._driver or not self.window_manager:
            raise BrowserManagementError(
                "Operação não permitida. O navegador não foi iniciado. Chame o método start() primeiro.")

    def _configure_driver_timeouts(self) -> None:
        if not self._driver:
            return
        timeouts = self.settings.get("timeouts", {})
        self._driver.set_page_load_timeout(timeouts.get("page_load_ms", 45000) / 1000.0)
        self._driver.set_script_timeout(timeouts.get("script_ms", 30000) / 1000.0)

    def _cleanup(self) -> None:
        self.stop(take_final_snapshot=False)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.error("Exceção não tratada no bloco 'with'. Tirando snapshot de erro.", exc_info=True)
            if self.settings.get("snapshots", {}).get("on_error", True):
                self.take_snapshot("unhandled_exception")
        self.stop()
