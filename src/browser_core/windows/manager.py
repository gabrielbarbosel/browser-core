# Define o sistema de gestão de janelas e abas.
#
# Este módulo introduz o WindowManager, responsável por criar e retornar
# objetos 'Tab' que permitem um controle orientado a objetos sobre cada aba
# do navegador.

from typing import Dict, Optional, TYPE_CHECKING

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from .tab import Tab
# A importação da exceção é feita aqui para maior clareza e robustez.
from ..exceptions import WorkerError, ConfigurationError

# Evita importação circular, mas permite o type hinting
if TYPE_CHECKING:
    from ..worker import Worker


class WindowManager:
    """
    Gere as janelas e abas do navegador, retornando objetos 'Tab' para controle.
    """

    def __init__(self, worker_instance: "Worker"):
        """
        Inicializa o gestor de janelas.
        """
        self._worker = worker_instance
        self._driver = worker_instance._driver
        self._logger = worker_instance.logger
        self._tabs: Dict[str, Tab] = {}
        self._tab_counter = 0
        self.sync_tabs()

    def sync_tabs(self) -> None:
        """Sincroniza o mapeamento interno com o estado real de abas do navegador."""
        if not self._driver: return

        window_handles = self._driver.window_handles
        if not window_handles:
            self._tabs = {}
            return

        main_handle = window_handles[0]
        new_tabs = {"main": Tab(name="main", handle=main_handle, worker=self._worker)}

        i = 1
        for handle in window_handles:
            if handle == main_handle: continue

            # Tenta preservar o nome antigo se o handle já era conhecido
            existing_name = next((name for name, tab in self._tabs.items() if tab.handle == handle), f"tab_{i}")
            new_tabs[existing_name] = Tab(name=existing_name, handle=handle, worker=self._worker)
            i += 1

        self._tabs = new_tabs
        self._logger.debug(f"Abas sincronizadas: {list(self._tabs.keys())}")

    def open_tab(self, name: Optional[str] = None) -> Tab:
        """
        Abre uma nova aba, alterna o foco para ela e retorna o objeto Tab controlador.
        Lança um erro se o nome fornecido já estiver em uso.
        """
        self._logger.info("Abrindo uma nova aba...")

        # Validação para impedir nomes duplicados
        if name and name in self._tabs:
            raise ConfigurationError(
                f"O nome de aba '{name}' já está em uso. Os nomes das abas devem ser únicos."
            )

        known_handles_before = set(self._driver.window_handles)
        self._driver.execute_script("window.open('');")

        try:
            WebDriverWait(self._driver, timeout=10).until(
                lambda d: set(d.window_handles) - known_handles_before
            )
        except TimeoutException:
            raise WorkerError("A nova aba não abriu dentro do tempo esperado.")

        new_handle = (set(self._driver.window_handles) - known_handles_before).pop()

        self._tab_counter += 1
        tab_name = name if name else f"tab_{self._tab_counter}"

        new_tab = Tab(name=tab_name, handle=new_handle, worker=self._worker)
        self._tabs[tab_name] = new_tab

        self._logger.info(f"Nova aba aberta e nomeada como '{tab_name}'.")
        new_tab.switch_to()
        return new_tab

    def get_tab(self, name: str) -> Optional[Tab]:
        """Retorna o objeto Tab com base no seu nome."""
        return self._tabs.get(name)

    def get_current_tab_object(self) -> Optional[Tab]:
        """Retorna o objeto Tab da aba que está atualmente em foco."""
        current_handle = self._driver.current_window_handle
        for tab in self._tabs.values():
            if tab.handle == current_handle:
                return tab
        return None

    def switch_to_tab(self, name: str) -> None:
        """Alterna o foco para uma aba específica pelo seu nome."""
        target_tab = self.get_tab(name)
        if not target_tab:
            raise WorkerError(f"A aba com o nome '{name}' não foi encontrada.")

        if target_tab.handle not in self._driver.window_handles:
            self._logger.warning(f"A aba '{name}' não existe mais no navegador. Sincronizando.")
            self.sync_tabs()
            target_tab = self.get_tab(name)  # Tenta obter novamente após a sincronização
            if not target_tab:
                raise WorkerError(f"A aba '{name}' foi fechada ou nunca existiu.")

        self._driver.switch_to.window(target_tab.handle)

    def close_tab(self, name: Optional[str] = None) -> None:
        """Fecha uma aba. Se nenhum nome for fornecido, fecha a aba atual."""
        if name:
            target_tab = self.get_tab(name)
            if not target_tab:
                self._logger.warning(f"Tentativa de fechar uma aba inexistente: '{name}'")
                return
        else:
            target_tab = self.get_current_tab_object()
            if not target_tab:
                self._logger.warning("Não foi possível determinar a aba atual para fechar.")
                return

        tab_name_to_delete = target_tab.name
        self._logger.info(f"Fechando a aba '{tab_name_to_delete}'...")

        # Foca na aba para fechá-la
        self._driver.switch_to.window(target_tab.handle)
        self._driver.close()

        # Remove a aba do nosso mapeamento
        if tab_name_to_delete in self._tabs:
            del self._tabs[tab_name_to_delete]

        # Foca de volta na aba principal por segurança, se ela ainda existir
        if "main" in self._tabs and self._tabs["main"].handle in self._driver.window_handles:
            self.switch_to_tab("main")
        elif self._driver.window_handles:
            # Se a 'main' foi fechada, foca em qualquer outra aba restante
            self._driver.switch_to.window(self._driver.window_handles[0])
            self.sync_tabs()  # Sincroniza para garantir que nosso estado interno reflete a realidade
