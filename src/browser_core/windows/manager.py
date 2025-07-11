# Define o sistema de gestão de janelas e abas.
#
# Este módulo introduz o WindowManager, responsável por criar e retornar
# objetos 'Tab' que permitem um controle orientado a objetos sobre cada aba
# do navegador.

from typing import Dict, Optional, List, TYPE_CHECKING, cast

from selenium.common.exceptions import (
    TimeoutException,
    NoSuchWindowException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .tab import Tab
from ..exceptions import BrowserManagementError

# Evita importação circular, mas permite o type hinting com a classe correta.
if TYPE_CHECKING:
    from ..orchestration.worker import Worker


class WindowManager:
    """
    Gerencia as janelas e abas do navegador, retornando objetos 'Tab' para controle.

    Abstrai as operações de baixo nível do WebDriver, permitindo abrir, fechar e
    alternar o foco entre abas de forma controlada e orientada a objetos.
    """

    def __init__(self, worker_instance: "Worker"):
        """
        Inicializa o gestor de janelas.

        Args:
            worker_instance: A instância principal da classe Worker.
                             É necessária para delegar ações como navegação e
                             execução de roteiros.
        """
        self._worker = worker_instance
        self._driver = self._worker.driver
        self._logger = self._worker.logger
        self._tabs: Dict[str, Tab] = {}
        self._tab_counter = 0
        self.sync_tabs()

    @property
    def current_tab_handle(self) -> Optional[str]:
        """Retorna o handle da aba atualmente em foco."""
        try:
            return self._driver.current_window_handle
        except NoSuchWindowException:
            self._logger.warning(
                "Não foi possível obter o handle da janela atual, o navegador pode ter sido fechado."
            )
            return None

    @property
    def known_handles(self) -> List[str]:
        """Retorna uma lista de todos os handles de abas conhecidos."""
        return [tab.handle for tab in self._tabs.values()]

    def get_current_tab_object(self) -> Optional[Tab]:
        """Retorna o objeto Tab que corresponde à aba atualmente em foco no navegador."""
        current_handle = self.current_tab_handle
        if not current_handle:
            return None
        for tab in self._tabs.values():
            if tab.handle == current_handle:
                return tab
        return None

    def sync_tabs(self) -> None:
        """
        Sincroniza o mapeamento interno de abas com o estado real do navegador,
        criando ou atualizando os objetos Tab.
        """
        self._logger.debug("Sincronizando handles de abas com o navegador.")
        try:
            handles_no_navegador = self._driver.window_handles
        except WebDriverException:
            self._logger.warning(
                "Falha ao obter os handles das janelas. O navegador pode não estar mais ativo."
            )
            handles_no_navegador = []

        self._tab_counter = len(handles_no_navegador)

        # Mapeamento padrão: 'main' para a primeira, 'tab_X' para as outras
        self._tabs = {
            ("main" if i == 0 else f"tab_{i}"): Tab(
                name=("main" if i == 0 else f"tab_{i}"),
                handle=handle,
                worker=self._worker,  # Passa a instância do Worker para a Tab
            )
            for i, handle in enumerate(handles_no_navegador)
        }
        self._logger.info(f"Abas sincronizadas: {list(self._tabs.keys())}")

    def open_tab(self, name: Optional[str] = None) -> Tab:
        """
        Abre uma nova aba, alterna o foco para ela e retorna o objeto Tab controlador.

        Args:
            name: Um nome opcional para identificar a aba (ex: "relatórios").

        Returns:
            O objeto Tab que controla a nova aba.
        """
        self._logger.info("Abrindo uma nova aba...")
        previous_handles = set(self._driver.window_handles)
        self._driver.execute_script("window.open('');")

        timeout_ms = self._worker.settings.get("timeouts", {}).get(
            "window_management_ms", 10_000
        )
        timeout_sec = timeout_ms / 1_000.0

        try:
            wait = WebDriverWait(cast(WebDriver, self._driver), timeout=timeout_sec)
            wait.until(EC.number_of_windows_to_be(len(previous_handles) + 1))
        except TimeoutException:
            raise BrowserManagementError(
                f"A nova aba não abriu dentro do tempo esperado de {timeout_sec}s."
            )

        # Identifica o handle da nova aba
        new_handle = (set(self._driver.window_handles) - previous_handles).pop()

        if name:
            tab_name = name
            if name in self._tabs:
                self._logger.warning(
                    f"O nome de aba '{name}' já existe. Será sobrescrito."
                )
        else:
            self._tab_counter += 1
            tab_name = f"tab_{self._tab_counter}"

        new_tab = Tab(name=tab_name, handle=new_handle, worker=self._worker)
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
            self._logger.warning(
                f"Aba '{name}' não encontrada ou handle inválido. Tentando sincronizar..."
            )
            self.sync_tabs()
            target_tab = self.get_tab(name)
            if not target_tab:
                raise BrowserManagementError(
                    f"A aba com o nome '{name}' não foi encontrada, mesmo após a sincronização."
                )

        self._logger.info(f"Alternando foco para a aba: '{name}'")
        self._driver.switch_to.window(target_tab.handle)

    def close_tab(self, name: Optional[str] = None) -> None:
        """Fecha uma aba específica. Se nenhum nome for fornecido, fecha a aba atual."""
        if name:
            target_tab = self.get_tab(name)
            if not target_tab:
                self._logger.warning(
                    f"Tentativa de fechar uma aba inexistente: '{name}'"
                )
                return
        else:
            # Pega a aba atual para fechar
            target_tab = self.get_current_tab_object()
            if not target_tab:
                self._logger.warning(
                    "Não foi possível determinar a aba atual para fechar."
                )
                return
            name = target_tab.name
            self._logger.info(f"Fechando a aba atual: '{name}'.")

        if len(self._driver.window_handles) > 1:
            self.switch_to_tab(name)
            self._driver.close()
        else:
            # Não fecha a última aba, pois isso fecharia o navegador.
            self._logger.warning(
                "Tentativa de fechar a última aba. A ação foi ignorada para não encerrar o navegador."
            )
            return

        if name in self._tabs:
            del self._tabs[name]

        # Sincroniza e volta para a aba principal por segurança
        # Isso garante que o controle nunca fique "perdido"
        self.sync_tabs()
        if "main" in self._tabs:
            self.switch_to_tab("main")
