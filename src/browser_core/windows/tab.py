# Contém a classe que representa e controla uma única aba do navegador.

from typing import TYPE_CHECKING, Any

# Evita importação circular, permitindo que o type checker entenda a classe Browser
if TYPE_CHECKING:
    from ..browser import Browser


class Tab:
    """Representa e controla uma única aba do navegador de forma orientada a objetos."""

    def __init__(self, name: str, handle: str, browser: "Browser"):
        self.name = name
        self.handle = handle
        self._browser = browser
        self._logger = browser.logger

    def switch_to(self) -> "Tab":
        """Muda o foco do navegador para esta aba e a retorna."""
        self._logger.debug(f"Mudando foco para a aba '{self.name}'.")
        self._browser.switch_to_tab(self.name)
        return self

    def navigate_to(self, url: str) -> "Tab":
        """Navega esta aba para uma nova URL."""
        self.switch_to()
        self._browser.navigate_to(url)
        return self

    def close(self) -> None:
        """Fecha esta aba."""
        self._browser.close_tab(self.name)

    @property
    def current_url(self) -> str:
        """Retorna a URL atual desta aba."""
        self.switch_to()  # Garante que o foco está na aba correta
        # noinspection PyProtectedMember
        return self._browser._driver.current_url

    def __repr__(self) -> str:
        return f"<Tab name='{self.name}' handle='{self.handle}'>"
