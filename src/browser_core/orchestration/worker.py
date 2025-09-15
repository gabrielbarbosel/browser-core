import time
import psutil
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, Tuple

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..engines import (
    AutomationEngine,
    SeleniumChromeEngine,
)
from ..exceptions import WorkerError, PageLoadError, BrowserManagementError
from ..logging import TaskLoggerAdapter
from ..selectors.element_proxy import ElementProxy
from ..selectors.multi_proxy import ElementListProxy
from ..selectors.manager import SelectorDefinition, SelectorManager
from ..settings import Settings
from ..types import DriverInfo, WebElementProtocol
from ..utils import ensure_directory
from ..windows.manager import WindowManager
from ..windows.tab import Tab


class Worker:
    """
    Orquestra as operações de automação de um único navegador.
    """

    def __init__(
        self,
        worker_id: str,
        driver_info: DriverInfo,
        profile_dir: Path,
        logger: "TaskLoggerAdapter",
        settings: Settings,
        engine: Optional[AutomationEngine] = None,
        debug_artifacts_dir: Optional[Path] = None,
    ):
        """
        Inicializa a instância do Worker.
        """
        self.worker_id = worker_id
        self.settings = settings
        self.driver_info = driver_info
        self.profile_dir = profile_dir
        self.logger = logger
        self.debug_artifacts_dir = debug_artifacts_dir or (
            self.profile_dir / "debug_artifacts"
        )

        self._driver: Optional[Any] = None
        self.driver_pid: Optional[int] = None
        self._is_started = False

        self.selector_manager = SelectorManager(
            logger=self.logger, settings=self.settings
        )

        self._engine: AutomationEngine = engine or SeleniumChromeEngine(
            self, self.settings.get("browser", {})
        )

        self.logger.worker_instance = self
        self.logger.info("Instância de Worker criada e pronta para iniciar.")

    def set_engine(self, engine: AutomationEngine) -> None:
        """Define ou substitui o engine de automação do worker."""
        self._engine = engine

    @property
    def driver(self) -> Any:
        """Propriedade pública para aceder de forma segura à instância do driver."""
        self._ensure_started()
        return self._driver

    @property
    def window_manager(self) -> WindowManager:
        self._ensure_started()
        return self._engine.window_manager

    @property
    def is_running(self) -> bool:
        """Verifica se o worker e o driver estão ativos."""
        return self._is_started and self._driver is not None

    # --- Métodos de Ciclo de Vida ---

    def start(self) -> None:
        """Inicia o WebDriver e os gestores necessários para a automação."""
        if self._is_started:
            self.logger.warning(
                "O método start() foi chamado, mas o worker já está iniciado."
            )
            return

        self.logger.info("Iniciando o worker e a sessão do navegador...")
        try:
            start_time = time.time()
            if not self._engine:
                raise WorkerError("Engine não configurado")

            self._driver, self.driver_pid = self._engine.start(self.profile_dir)
            # Enhanced stealth injection for anti-bot detection
            try:
                browser_cfg = self.settings.get("browser", {})
                if browser_cfg.get("stealth"):
                    self.logger.info(f"[{self.worker_id}] Ativando modo stealth...")
                    self.execute_script(
                        """
                        // Enhanced anti-detection measures
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR','pt','en'] });
                        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
                        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
                        Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
                        
                        // Override automation detection
                        Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }) });
                        Object.defineProperty(navigator, 'permissions', { 
                            get: () => ({
                                query: (params) => Promise.resolve({ state: 'granted' })
                            })
                        });
                        
                        // Override WebRTC fingerprinting
                        Object.defineProperty(navigator, 'mediaDevices', { 
                            get: () => ({
                                enumerateDevices: () => Promise.resolve([])
                            })
                        });
                        
                        // Override canvas fingerprinting
                        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                        HTMLCanvasElement.prototype.toDataURL = function() {
                            const context = this.getContext('2d');
                            if (context) {
                                const imageData = context.getImageData(0, 0, this.width, this.height);
                                for (let i = 0; i < imageData.data.length; i += 4) {
                                    imageData.data[i] = imageData.data[i] + Math.floor(Math.random() * 10) - 5;
                                    imageData.data[i + 1] = imageData.data[i + 1] + Math.floor(Math.random() * 10) - 5;
                                    imageData.data[i + 2] = imageData.data[i + 2] + Math.floor(Math.random() * 10) - 5;
                                }
                                context.putImageData(imageData, 0, 0);
                            }
                            return originalToDataURL.apply(this, arguments);
                        };
                        
                        // Override WebGL fingerprinting
                        const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
                        WebGLRenderingContext.prototype.getParameter = function(parameter) {
                            if (parameter === 37445) return 'Intel Inc.';
                            if (parameter === 37446) return 'Intel(R) HD Graphics 620';
                            return originalGetParameter.apply(this, arguments);
                        };
                        
                        // Override audio context fingerprinting
                        const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
                        AudioContext.prototype.createAnalyser = function() {
                            const analyser = originalCreateAnalyser.apply(this, arguments);
                            const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;
                            analyser.getFloatFrequencyData = function(array) {
                                originalGetFloatFrequencyData.apply(this, arguments);
                                for (let i = 0; i < array.length; i++) {
                                    array[i] = array[i] + Math.random() * 0.0001;
                                }
                            };
                            return analyser;
                        };
                        
                        // Override battery API
                        Object.defineProperty(navigator, 'getBattery', { 
                            get: () => () => Promise.resolve({
                                charging: true,
                                chargingTime: 0,
                                dischargingTime: Infinity,
                                level: 1
                            })
                        });
                        
                        // Override timezone
                        Object.defineProperty(Intl, 'DateTimeFormat', {
                            get: () => function() {
                                return {
                                    resolvedOptions: () => ({ timeZone: 'America/Sao_Paulo' })
                                };
                            }
                        });
                        
                        // Override screen properties
                        Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
                        Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
                        Object.defineProperty(screen, 'height', { get: () => 1080 });
                        Object.defineProperty(screen, 'width', { get: () => 1920 });
                        Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
                        Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
                        
                        // Override connection properties
                        Object.defineProperty(navigator, 'connection', { 
                            get: () => ({
                                effectiveType: '4g',
                                rtt: 50,
                                downlink: 10
                            })
                        });
                        
                        // Override memory info
                        Object.defineProperty(performance, 'memory', { 
                            get: () => ({
                                usedJSHeapSize: 10000000,
                                totalJSHeapSize: 20000000,
                                jsHeapSizeLimit: 2000000000
                            })
                        });
                        
                        // Override notification permission
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                          parameters.name === 'notifications'
                            ? Promise.resolve({ state: Notification.permission })
                            : originalQuery(parameters)
                        );
                        
                        // Override automation indicators
                        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                        """
                    )
                    self.logger.info(f"[{self.worker_id}] Modo stealth ativado com sucesso.")
            except Exception as e:
                self.logger.warning(f"[{self.worker_id}] Falha ao ativar modo stealth: {e}")
                pass
            self._is_started = True
            duration = (time.time() - start_time) * 1_000
            self.logger.info(f"Worker iniciado com sucesso em {duration:.2f}ms.")
        except Exception as e:
            self.logger.error(f"Falha crítica ao iniciar o worker: {e}", exc_info=True)
            self.stop()
            raise WorkerError(f"Falha ao iniciar o worker: {e}", original_error=e)

    def stop(self) -> None:
        """Finaliza a sessão do WebDriver de forma limpa, garantindo o fim do processo."""
        if not self._is_started:
            return
        self.logger.info("Finalizando o worker...")
        try:
            if self._engine:
                self._engine.stop()
        finally:
            # Lógica de autolimpeza para garantir que o processo do driver seja encerrado
            if self.driver_pid and psutil.pid_exists(self.driver_pid):
                self.logger.warning(
                    f"O processo do driver (PID: {self.driver_pid}) não foi finalizado corretamente. A forçar o encerramento."
                )
                try:
                    proc = psutil.Process(self.driver_pid)
                    proc.kill()
                    self.logger.info(
                        f"Processo do driver (PID: {self.driver_pid}) finalizado com sucesso."
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    self.logger.error(
                        f"Falha ao tentar finalizar o processo do driver (PID: {self.driver_pid}): {e}"
                    )

            self._driver = None
            self.driver_pid = None
            self._is_started = False
            self.logger.info("Worker finalizado e recursos do navegador libertados.")

    # --- Métodos de Interação com a Página ---

    def navigate_to(self, url: str) -> None:
        """Navega a aba atual para uma URL especificada."""
        self._ensure_started()
        self.logger.info(f"Navegando para a URL: {url}")
        try:
            if not self._engine:
                raise WorkerError("Engine não configurado")
            self._engine.navigate_to(url)
        except WebDriverException as e:
            timeout_ms = self.settings.get("timeouts", {}).get("page_load_ms", 45_000)
            raise PageLoadError(
                f"Falha ao carregar a URL: {url}",
                context={"url": url, "timeout_ms": timeout_ms},
                original_error=e,
            )

    def wait_for_url_contains(self, substring: str, timeout_ms: int) -> None:
        """Espera até que a URL atual contenha o texto informado."""
        self._ensure_started()
        WebDriverWait(self.driver, timeout_ms / 1000).until(EC.url_contains(substring))

    def wait_for_page_title(self, title: str, timeout_ms: int) -> None:
        """Espera até que o título da página corresponda ao texto."""
        self._ensure_started()
        WebDriverWait(self.driver, timeout_ms / 1000).until(EC.title_is(title))

    def get(self, definition: SelectorDefinition) -> "ElementProxy":
        """
        Retorna um objeto proxy para um elemento, permitindo a execução de ações fluentes.
        """
        self._ensure_started()
        return ElementProxy(self, definition)

    def get_all(self, definition: SelectorDefinition) -> "ElementListProxy":
        """Retorna uma lista de ElementProxy para todos os elementos encontrados."""
        self._ensure_started()
        elements = self.selector_manager.find_elements(self.driver, definition)
        proxies = [ElementProxy(self, definition) for _ in elements]
        for proxy, element in zip(proxies, elements):
            proxy._element = element
            proxy._used_selector = definition.primary
        return ElementListProxy(proxies)

    def find_element(self, definition: SelectorDefinition) -> WebElementProtocol:
        """
        Encontra um elemento na página e o retorna imediatamente.
        """
        self._ensure_started()
        if not self._engine:
            raise WorkerError("Engine não configurado")
        return self._engine.find_element(definition)

    def execute_script(self, script: str, *args: Any) -> Any:
        """Executa um roteiro JavaScript no contexto da página atual."""
        self._ensure_started()
        if not self._engine:
            raise WorkerError("Engine não configurado")
        return self._engine.execute_script(script, *args)

    # --- Métodos de controle de iframe ---

    def switch_to_iframe(
        self, frame_reference: Union[str, int, "ElementProxy", WebElement]
    ) -> None:
        """
        Muda o foco do driver para um iframe específico.
        """
        self._ensure_started()
        target = frame_reference
        if isinstance(frame_reference, ElementProxy):
            target = frame_reference.get_element()

        self.logger.info(f"Mudando contexto para o iframe: '{frame_reference}'")
        try:
            self.driver.switch_to.frame(target)
        except Exception as e:
            raise BrowserManagementError(
                f"Não foi possível mudar para o iframe '{frame_reference}'",
                original_error=e,
            )

    def switch_to_default_content(self) -> None:
        """
        Retorna o foco do driver para o contexto principal da página.
        """
        self._ensure_started()
        self.logger.info("Retornando para o contexto principal da página.")
        self.driver.switch_to.default_content()

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

    def capture_debug_artifacts(
        self, name: str, exc_info: Optional[Tuple] = None
    ) -> Optional[Path]:
        """
        Captura um conjunto rico de artefatos de depuração do estado atual.
        """
        if not self.is_running:
            self.logger.warning(
                "Não é possível capturar artefatos, o worker não está iniciado."
            )
            return None

        try:
            artifacts_dir = ensure_directory(self.debug_artifacts_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            capture_name = f"{timestamp}_{name}"
            capture_path = ensure_directory(artifacts_dir / capture_name)

            debug_context = {
                "capture_time": datetime.now().isoformat(),
                "worker_id": self.worker_id,
                "current_url": self._driver.current_url,
                "page_title": self._driver.title,
                "window_handles": self._driver.window_handles,
                "current_window_handle": self._driver.current_window_handle,
            }

            if exc_info:
                exc_type, exc_val, exc_tb = exc_info
                debug_context["exception"] = {
                    "type": str(exc_type.__name__),
                    "message": str(exc_val),
                    "traceback": "".join(
                        traceback.format_exception(exc_type, exc_val, exc_tb)
                    ),
                }

            # 1. Salva o Screenshot
            screenshot_file = capture_path / "screenshot.png"
            self._driver.save_screenshot(str(screenshot_file))

            # 2. Salva o DOM da página
            dom_file = capture_path / "dom.html"
            with open(dom_file, "w", encoding="utf-8") as f:
                f.write(self._driver.page_source)

            # 3. Salva os logs do console do navegador
            try:
                console_logs = self._driver.get_log("browser")
                logs_file = capture_path / "browser_console.json"
                with open(logs_file, "w", encoding="utf-8") as f:
                    json.dump(console_logs, f, indent=2, ensure_ascii=False)
            except Exception as log_e:
                self.logger.warning(
                    f"Não foi possível capturar os logs do console do navegador: {log_e}"
                )
                debug_context["console_logs_error"] = str(log_e)

            # 4. Salva o arquivo de manifesto com todo o contexto
            context_file = capture_path / "debug_context.json"
            with open(context_file, "w", encoding="utf-8") as f:
                json.dump(debug_context, f, indent=2, ensure_ascii=False)

            self.logger.info(
                f"Artefatos de depuração '{name}' capturados em: {capture_path}"
            )
            return capture_path
        except Exception as e:
            self.logger.error(
                f"Falha ao capturar os artefatos de depuração '{name}': {e}",
                exc_info=True,
            )
            return None

    def _ensure_started(self) -> None:
        """Garante que o worker foi iniciado antes de qualquer operação."""
        if not self.is_running:
            raise WorkerError("Operação não permitida. O worker não foi iniciado.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Garante que o worker seja finalizado e os erros capturados."""
        if exc_type:
            self.logger.error(
                "Exceção não tratada dentro do bloco 'with' do worker.",
                exc_info=(exc_type, exc_val, exc_tb),
            )
            self.capture_debug_artifacts(
                "unhandled_exception", exc_info=(exc_type, exc_val, exc_tb)
            )
        self.stop()
