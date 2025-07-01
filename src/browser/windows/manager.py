# Define o sistema de gestão de janelas e abas.
#
# Este módulo introduz o WindowManager, responsável por rastrear,
# focar e gerir o ciclo de vida de múltiplas janelas e abas
# numa sessão de automação, usando uma nomenclatura amigável.

from typing import Dict, Optional, List

from ..types import WebDriverProtocol, LoggerProtocol
from ..exceptions import BrowserManagementError


class WindowManager:
    """
    Gere as janelas e abas do navegador.

    Abstrai as operações de baixo nível do WebDriver para manipulação
    de janelas, permitindo abrir, fechar e alternar o foco entre
    elas de forma controlada através de nomes (aliases).
    """

    def __init__(self, driver: WebDriverProtocol, logger: LoggerProtocol):
        """
        Inicializa o gestor de janelas.

        Args:
            driver: A instância do WebDriver a ser controlada.
            logger: A instância do logger para registar as operações.
        """
        self._driver = driver
        self._logger = logger
        # Mapeia um alias/nome para o respetivo handle de janela.
        self._tabs: Dict[str, str] = {}
        self.sync_tabs()

    @property
    def current_tab_handle(self) -> Optional[str]:
        """Retorna o handle da aba atualmente em foco."""
        return self._driver.current_window_handle

    @property
    def known_handles(self) -> List[str]:
        """Retorna uma lista de todos os handles de abas conhecidos."""
        return list(self._tabs.values())

    def sync_tabs(self) -> None:
        """
        Sincroniza o mapeamento interno de abas com o estado real do navegador.
        """
        self._logger.debug("A sincronizar handles de abas com o navegador.")
        handles_no_navegador = self._driver.window_handles

        # Mapeamento padrão: 'main' para a primeira, 'tab_1', 'tab_2', etc.
        self._tabs = {
            f"tab_{i}" if i > 0 else "main": handle
            for i, handle in enumerate(handles_no_navegador)
        }
        self._logger.info(f"Abas sincronizadas: {self._tabs}")

    def open_tab(self, name: Optional[str] = None) -> str:
        """
        Abre uma nova aba, alterna o foco para ela e atribui-lhe um nome.

        Args:
            name: Um nome opcional para identificar a aba (ex: "relatorios").

        Returns:
            O nome (alias) da nova aba.
        """
        self._logger.info("A abrir uma nova aba...")
        self._driver.execute_script("window.open('');")

        # Encontra o novo handle que não estava na lista anterior
        previous_handles = set(self.known_handles)
        current_handles = set(self._driver.window_handles)
        new_handle = (current_handles - previous_handles).pop()

        self._driver.switch_to.window(new_handle)

        # Determina o nome para a nova aba
        if name and name in self._tabs:
            self._logger.warning(f"O nome de aba '{name}' já existe. Será sobrescrito.")

        tab_name = name or f"tab_{len(self._tabs)}"
        self._tabs[tab_name] = new_handle

        self._logger.info(f"Nova aba aberta e nomeada como '{tab_name}'.")
        return tab_name

    def switch_to_tab(self, name: str) -> None:
        """
        Alterna o foco para uma aba específica pelo seu nome.

        Args:
            name: O nome (alias) da aba para a qual alternar.
        """
        target_handle = self._tabs.get(name)
        if not target_handle or target_handle not in self._driver.window_handles:
            self.sync_tabs()  # Tenta sincronizar caso o estado tenha mudado
            target_handle = self._tabs.get(name)
            if not target_handle:
                raise BrowserManagementError(f"A aba com o nome '{name}' não foi encontrada.")

        self._logger.info(f"A alternar foco para a aba: '{name}'")
        self._driver.switch_to.window(target_handle)

    def close_tab(self, name: Optional[str] = None) -> None:
        """
        Fecha uma aba específica. Se nenhum nome for fornecido, fecha a aba atual.

        Args:
            name: O nome (alias) da aba a ser fechada.
        """
        if name:
            target_handle = self._tabs.get(name)
            if not target_handle:
                self._logger.warning(f"Tentativa de fechar uma aba inexistente: '{name}'")
                return
        else:
            target_handle = self.current_tab_handle
            self._logger.info("Nenhum nome fornecido. A fechar a aba atual.")

        # Alterna para a aba para garantir que a aba correta é fechada
        self._driver.switch_to.window(target_handle)
        self._driver.close()

        # Remove a aba fechada do mapeamento
        if name and name in self._tabs:
            del self._tabs[name]

        # Sincroniza e volta para a aba principal por segurança
        self.sync_tabs()
        if "main" in self._tabs:
            self.switch_to_tab("main")
