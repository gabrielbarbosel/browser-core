# Contém a classe que representa e controla uma única aba do navegador.

from typing import TYPE_CHECKING, Any

# A importação agora aponta para a nova classe 'Worker' para type hinting.
if TYPE_CHECKING:
    from ..worker import Worker


class Tab:
    """Representa e controla uma única aba do navegador de forma orientada a objetos."""

    def __init__(self, name: str, handle: str, worker: "Worker"):
        """
        Inicializa o objeto Tab.

        Args:
            name: O nome lógico da aba (ex: "main", "relatorios").
            handle: O identificador da janela/aba fornecido pelo WebDriver.
            worker: A instância do Worker que controla esta aba.
        """
        self.name = name
        self.handle = handle
        # A referência interna agora é para um 'Worker', não um 'Browser'.
        self._worker = worker
        self._logger = worker.logger

    def switch_to(self) -> "Tab":
        """Muda o foco do navegador para esta aba e a retorna."""
        self._logger.debug(f"Mudando foco para a aba '{self.name}'.")
        # Delega a troca de aba para o worker.
        self._worker.switch_to_tab(self.name)
        return self

    def navigate_to(self, url: str) -> "Tab":
        """Navega esta aba para uma nova URL."""
        # Garante que esta aba está ativa antes de navegar.
        self.switch_to()
        self._worker.navigate_to(url)
        return self

    def close(self) -> None:
        """Fecha esta aba."""
        # Delega o fechamento para o worker.
        self._worker.close_tab(self.name)

    @property
    def current_url(self) -> str:
        """Retorna a URL atual desta aba."""
        # Garante que estamos a verificar a URL da aba correta.
        self.switch_to()
        # Acessa o driver através da instância do worker.
        # noinspection PyProtectedMember
        return self._worker._driver.current_url

    def __repr__(self) -> str:
        return f"<Tab name='{self.name}' handle='{self.handle}'>"
