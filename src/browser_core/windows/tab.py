# Contém a classe que representa e controla uma única aba do navegador.

from typing import TYPE_CHECKING

# Evita importação circular, permitindo que o type checker entenda a classe Worker.
if TYPE_CHECKING:
    from ..orchestration.worker import Worker


# noinspection GrazieInspection
class Tab:
    """Representa e controla uma única aba do navegador de forma orientada a objetos."""

    def __init__(self, name: str, handle: str, worker: "Worker"):
        # noinspection SpellCheckingInspection
        """
        Inicializa a representação de uma aba.

        Args:
            name: O nome lógico da aba (ex: 'main', 'relatórios').
            handle: O identificador único da aba fornecido pelo WebDriver.
            worker: A instância do Worker que gerencia esta aba.
        """
        self.name = name
        self.handle = handle
        self._worker = worker
        self._logger = worker.logger

    def switch_to(self) -> "Tab":
        """Muda o foco do navegador para esta aba e a retorna."""
        self._logger.debug(f"Mudando foco para a aba '{self.name}'.")
        # A lógica de troca de aba agora é centralizada no worker.
        self._worker.window_manager.switch_to_tab(self.name)
        return self

    def navigate_to(self, url: str) -> "Tab":
        """Navega esta aba para uma nova URL."""
        self.switch_to()
        # Delega a navegação para o método do worker.
        self._worker.navigate_to(url)
        return self

    def close(self) -> None:
        """Fecha esta aba."""
        # Delega o fechamento para o método do worker.
        self._worker.window_manager.close_tab(self.name)

    @property
    def current_url(self) -> str:
        """Retorna a URL atual desta aba."""
        self.switch_to()  # Garante que o foco está na aba correta.
        return self._worker.driver.current_url

    def __repr__(self) -> str:
        return f"<Tab name='{self.name}' handle='{self.handle}'>"
