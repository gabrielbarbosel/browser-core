# Define o sistema de gestão de janelas e abas.
#
# Este módulo introduz o WindowManager, responsável por criar e retornar
# objetos 'Tab' que permitem um controle orientado a objetos sobre cada aba
# do navegador.

from typing import Dict, Optional, List, TYPE_CHECKING
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..exceptions import BrowserManagementError
from .tab import Tab  # Importa a nova classe que representa uma aba

# Evita importação circular, mas permite o type hinting
if TYPE_CHECKING:
    from ..browser import Browser


class WindowManager:
    """
    Gere as janelas e abas do navegador, retornando objetos 'Tab' para controle.

    Abstrai as operações de baixo nível do WebDriver, permitindo abrir, fechar e
    alternar o foco entre abas de forma controlada e orientada a objetos.
    """

    def __init__(self, browser_instance: "Browser"):
        """
        Inicializa o gestor de janelas.

        Args:
            browser_instance: A instância principal da classe Browser.
                              É necessária para delegar ações como navegação e
                              execução de scripts.
        """
        self._browser = browser_instance
        # noinspection PyProtectedMember
        self._driver = browser_instance._driver
        self._logger = browser_instance.logger
        # O dicionário agora armazena o nome da aba e o objeto Tab correspondente
        self._tabs: Dict[str, Tab] = {}
        self._tab_counter = 0
        self.sync_tabs()

    @property
    def current_tab_handle(self) -> Optional[str]:
        """Retorna o handle da aba atualmente em foco."""
        return self._driver.current_window_handle

    @property
    def known_handles(self) -> List[str]:
        """Retorna uma lista de todos os handles de abas conhecidos."""
        return [tab.handle for tab in self._tabs.values()]

    def sync_tabs(self) -> None:
        """
        Sincroniza o mapeamento interno de abas com o estado real do navegador,
        criando ou atualizando os objetos Tab.
        """
        self._logger.debug("Sincronizando handles de abas com o navegador.")
        handles_no_navegador = self._driver.window_handles
        self._tab_counter = len(handles_no_navegador)

        # Mapeamento padrão: 'main' para a primeira, 'tab_X' para as outras
        self._tabs = {
            ("main" if i == 0 else f"tab_{i}"): Tab(
                name=("main" if i == 0 else f"tab_{i}"),
                handle=handle,
                browser=self._browser
            )
            for i, handle in enumerate(handles_no_navegador)
        }
        self._logger.info(f"Abas sincronizadas: {list(self._tabs.keys())}")

    def open_tab(self, name: Optional[str] = None) -> Tab:
        """
        Abre uma nova aba, alterna o foco para ela e retorna o objeto Tab controlador.

        Args:
            name: Um nome opcional para identificar a aba (ex: "relatorios").

        Returns:
            O objeto Tab que controla a nova aba.
        """
        self._logger.info("Abrindo uma nova aba...")
        previous_handles_count = len(self._driver.window_handles)
        self._driver.execute_script("window.open('');")

        try:
            wait = WebDriverWait(self._driver, timeout=10)  # Espera até 10 segundos
            wait.until(EC.number_of_windows_to_be(previous_handles_count + 1))
        except TimeoutException:
            raise BrowserManagementError("A nova aba não abriu dentro do tempo esperado.")

        # Identifica o handle da nova aba
        new_handle = [h for h in self._driver.window_handles if h not in self.known_handles][0]

        if name:
            tab_name = name
            if name in self._tabs:
                self._logger.warning(f"O nome de aba '{name}' já existe. Será sobrescrito.")
        else:
            self._tab_counter += 1
            tab_name = f"tab_{self._tab_counter}"

        new_tab = Tab(name=tab_name, handle=new_handle, browser=self._browser)
        self._tabs[tab_name] = new_tab

        self._logger.info(f"Nova aba aberta e nomeada como '{tab_name}'.")
        new_tab.switch_to()
        return new_tab

    def get_tab(self, name: str) -> Optional[Tab]:
        """Retorna o objeto Tab com base no seu nome."""
        return self._tabs.get(name)

    def switch_to_tab(self, name: str) -> None:
        """Alterna o foco para uma aba específica pelo seu nome."""
        target_tab = self.get_tab(name)
        if not target_tab or target_tab.handle not in self._driver.window_handles:
            self.sync_tabs()  # Tenta sincronizar caso o estado tenha mudado
            target_tab = self.get_tab(name)
            if not target_tab:
                raise BrowserManagementError(f"A aba com o nome '{name}' não foi encontrada.")

        self._logger.info(f"Alternando foco para a aba: '{name}'")
        self._driver.switch_to.window(target_tab.handle)

    def close_tab(self, name: Optional[str] = None) -> None:
        """Fecha uma aba específica. Se nenhum nome for fornecido, fecha a aba atual."""
        if name:
            target_tab = self.get_tab(name)
            if not target_tab:
                self._logger.warning(f"Tentativa de fechar uma aba inexistente: '{name}'")
                return
        else:
            # Pega a aba atual para fechar
            target_tab = self._browser.current_tab
            if not target_tab:
                self._logger.warning("Não foi possível determinar a aba atual para fechar.")
                return
            name = target_tab.name
            self._logger.info(f"Fechando a aba atual: '{name}'.")

        # Delegação final
        self._driver.switch_to.window(target_tab.handle)
        self._driver.close()

        if name in self._tabs:
            del self._tabs[name]

        # Sincroniza e volta para a aba principal por segurança
        # Isso garante que o controle nunca fique "perdido"
        self.sync_tabs()
        if "main" in self._tabs:
            self.switch_to_tab("main")
