# Define a unidade de execução de automação, o Worker.

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from selenium.common.exceptions import WebDriverException

from .drivers.manager import DriverManager
from .exceptions import WorkerError, PageLoadError
from .logging import TaskLoggerAdapter
# Importa a nova classe de proxy
from .selectors.element_proxy import ElementProxy
from .selectors.manager import SelectorDefinition, SelectorManager
from .settings import Settings
from .types import DriverInfo, WebDriverProtocol
from .utils import ensure_directory
from .windows.manager import WindowManager
from .windows.tab import Tab


class Worker:
    """
    Orquestra as operações de automação de um único navegador.
    """

    def __init__(
            self,
            driver_info: DriverInfo,
            profile_dir: Path,
            logger: "TaskLoggerAdapter",
            settings: Settings,
            debug_artifacts_dir: Optional[Path] = None
    ):
        """
        Inicializa a instância do Worker.
        """
        self.settings = settings
        self.driver_info = driver_info
        self.profile_dir = profile_dir
        self.logger = logger
        self.debug_artifacts_dir = debug_artifacts_dir or (self.profile_dir / "debug_artifacts")

        self._driver: Optional[WebDriverProtocol] = None
        self._is_started = False

        self.driver_manager = DriverManager(logger=self.logger)
        self.selector_manager = SelectorManager(logger=self.logger)
        self.window_manager: Optional[WindowManager] = None

        self.logger.worker_instance = self
        self.logger.info("Instância de Worker criada e pronta para iniciar.")

    # --- Métodos de Ciclo de Vida ---

    def start(self) -> None:
        """Inicia o WebDriver e os gestores necessários para a automação."""
        if self._is_started:
            self.logger.warning("O método start() foi chamado, mas o worker já está iniciado.")
            return

        self.logger.info("Iniciando o worker e a sessão do navegador...")
        try:
            start_time = time.time()
            self._driver = self.driver_manager.create_driver(
                driver_info=self.driver_info,
                browser_config=self.settings.get("browser", {}),
                user_profile_dir=self.profile_dir,
            )
            self.window_manager = WindowManager(self)
            self._configure_driver_timeouts()
            self._is_started = True
            duration = (time.time() - start_time) * 1000
            self.logger.info(f"Worker iniciado com sucesso em {duration:.2f}ms.")
        except Exception as e:
            self.logger.error(f"Falha crítica ao iniciar o worker: {e}", exc_info=True)
            self.stop()
            raise WorkerError(f"Falha ao iniciar o worker: {e}", original_error=e)

    def stop(self) -> None:
        """Finaliza a sessão do WebDriver de forma limpa."""
        if not self._is_started or not self._driver:
            return
        self.logger.info("Finalizando o worker...")
        try:
            self._driver.quit()
        except Exception as e:
            self.logger.warning(f"Erro não crítico ao finalizar o WebDriver: {e}")
        finally:
            self._driver = None
            self._is_started = False
            self.logger.info("Worker finalizado e recursos do navegador libertados.")

    # --- Métodos de Interação com a Página ---

    def navigate_to(self, url: str) -> None:
        """Navega a aba atual para uma URL especificada."""
        self._ensure_started()
        self.logger.info(f"Navegando para a URL: {url}")
        try:
            self._driver.get(url)
        except WebDriverException as e:
            timeout_ms = self.settings.get("timeouts", {}).get("page_load_ms", 45000)
            raise PageLoadError(
                f"Falha ao carregar a URL: {url}",
                context={"url": url, "timeout_ms": timeout_ms},
                original_error=e
            )

    def get(self, definition: SelectorDefinition) -> "ElementProxy":
        """
        Retorna um objeto proxy para um elemento, permitindo a execução de ações fluentes.

        A busca real pelo elemento só ocorre quando uma ação (ex: .click()) é chamada.

        Args:
            definition: O objeto SelectorDefinition criado com `create_selector`.

        Returns:
            Uma instância de ElementProxy pronta para receber ações.
        """
        self._ensure_started()
        return ElementProxy(self, definition)

    def find_element(self, definition: SelectorDefinition) -> Any:
        """
        Encontra um elemento na página e o retorna imediatamente.

        Este método é usado internamente pelo ElementProxy. Para uso geral,
        prefira o método `get()` para uma API mais fluida.

        Args:
            definition: O objeto SelectorDefinition com os detalhes do seletor.

        Returns:
            O WebElement encontrado pelo Selenium.
        """
        self._ensure_started()
        return self.selector_manager.find_element(self._driver, definition)

    def execute_script(self, script: str, *args: Any) -> Any:
        """Executa um script JavaScript no contexto da página atual."""
        self._ensure_started()
        return self._driver.execute_script(script, *args)

    # --- Métodos de Gestão de Abas (Janelas) ---

    def open_tab(self, name: Optional[str] = None) -> Tab:
        """Abre uma nova aba e retorna o seu objeto controlador."""
        self._ensure_started()
        return self.window_manager.open_tab(name)

    def get_tab(self, name: str) -> Optional[Tab]:
        """Busca e retorna um objeto Tab pelo seu nome."""
        self._ensure_started()
        return self.window_manager.get_tab(name)

    @property
    def current_tab(self) -> Optional[Tab]:
        """Retorna o objeto Tab da aba que está atualmente em foco."""
        self._ensure_started()
        return self.window_manager.get_current_tab_object()

    def switch_to_tab(self, name: str) -> None:
        """Alterna o foco para uma aba usando seu nome."""
        self._ensure_started()
        self.window_manager.switch_to_tab(name)

    def close_tab(self, name: Optional[str] = None) -> None:
        """Fecha uma aba. Se nenhum nome for fornecido, fecha a aba atual."""
        self._ensure_started()
        self.window_manager.close_tab(name)

    # --- Métodos de Depuração e Internos ---

    def capture_debug_artifacts(self, name: str) -> Optional[Path]:
        """Captura artefatos de depuração do estado atual do navegador."""
        if not self._is_started:
            self.logger.warning("Não é possível capturar artefatos, o worker não está iniciado.")
            return None
        try:
            artifacts_dir = ensure_directory(self.debug_artifacts_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            capture_name = f"{timestamp}_{name}"
            capture_path = ensure_directory(artifacts_dir / capture_name)
            screenshot_file = capture_path / "screenshot.png"
            self._driver.save_screenshot(str(screenshot_file))
            dom_file = capture_path / "dom.html"
            with open(dom_file, "w", encoding="utf-8") as f:
                f.write(self._driver.page_source)
            self.logger.info(f"Artefatos de depuração '{name}' capturados em: {capture_path}")
            return capture_path
        except Exception as e:
            self.logger.error(f"Falha ao capturar os artefatos de depuração '{name}': {e}", exc_info=True)
            return None

    def _ensure_started(self) -> None:
        """Garante que o worker foi iniciado antes de qualquer operação."""
        if not self._is_started or not self._driver or not self.window_manager:
            raise WorkerError("Operação não permitida. O worker não foi iniciado.")

    def _configure_driver_timeouts(self) -> None:
        """Aplica as configurações de timeout ao driver."""
        timeouts = self.settings.get("timeouts", {})
        page_load_sec = timeouts.get("page_load_ms", 45000) / 1000.0
        script_sec = timeouts.get("script_ms", 30000) / 1000.0
        self._driver.set_page_load_timeout(page_load_sec)
        self._driver.set_script_timeout(script_sec)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Garante que o worker seja finalizado e os erros capturados."""
        if exc_type:
            self.logger.error(
                "Exceção não tratada dentro do bloco 'with' do worker.",
                exc_info=(exc_type, exc_val, exc_tb)
            )
            self.capture_debug_artifacts("unhandled_exception")
        self.stop()
