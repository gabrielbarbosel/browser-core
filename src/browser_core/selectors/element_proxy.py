# Define a classe ElementProxy para interações fluentes com elementos da web.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .manager import SelectorDefinition
from ..types import WebElementProtocol
from ..utils import mask_sensitive_data

# Evita importação circular, mantendo o type-hinting para a classe Worker.
if TYPE_CHECKING:
    from ..orchestration.worker import Worker


# noinspection GrazieInspection
class ElementProxy:
    """
    Representa um elemento da página de forma "preguiçosa" (lazy).

    A busca pelo elemento real no navegador só é realizada quando uma ação
    (como .click() ou .text) é invocada, permitindo uma API mais fluida.
    """

    def __init__(
        self,
        worker: "Worker",
        selector: SelectorDefinition,
        parent: Optional["ElementProxy"] = None,
    ):
        """
        Inicializa o proxy do elemento.

        Args:
            worker: A instância do Worker que irá executar as ações.
            selector: A definição do seletor para encontrar o elemento.
            parent: O ElementProxy pai, se for uma busca aninhada.
        """
        self._worker = worker
        self._selector = selector
        self._parent = parent
        self._element: Optional[WebElementProtocol] = None
        self._used_selector: Optional[str] = None  # Armazena o seletor que funcionou

    def _find(self) -> WebElementProtocol:
        """
        Garante que o elemento foi encontrado e o retorna.
        A busca é feita a partir do pai, se existir, ou do driver.
        """
        if self._element is None:
            search_context = (
                self._parent._find() if self._parent else self._worker.driver
            )

            #  A busca é feita pelo SelectorManager, que retorna o elemento e o seletor usado
            self._worker.logger.debug(
                f"ElementProxy: A procurar elemento com seletor '{self._selector.primary}'..."
            )
            self._element, self._used_selector = (
                self._worker.selector_manager.find_element(
                    search_context, self._selector
                )
            )
            self._worker.logger.debug(
                f"ElementProxy: Elemento encontrado com '{self._used_selector}' e cacheado."
            )

        return self._element

    @property
    def text(self) -> str:
        """Retorna o conteúdo de texto visível do elemento."""
        return self._find().text

    @property
    def tag_name(self) -> str:
        """Retorna o nome da tag do elemento."""
        return self._find().tag_name

    def get_attribute(self, name: str) -> str:
        """Retorna o valor de um atributo do elemento."""
        return self._find().get_attribute(name)

    def click(self) -> "ElementProxy":
        """Executa a ação de clique no elemento."""
        self._find()  # Garante que _used_selector seja preenchido
        self._worker.logger.info(
            f"A clicar no elemento definido por: '{self._used_selector}'"
        )
        self._element.click()
        return self

    def send_keys(self, *values: str) -> "ElementProxy":
        """
        Simula a digitação de texto no elemento, mascarando dados sensíveis no log.
        """
        text_to_send = "".join(values)
        masked_text = mask_sensitive_data(text_to_send)

        self._find()  # Garante que _used_selector seja preenchido
        self._worker.logger.info(
            f"A enviar texto '{masked_text}' para o elemento: '{self._used_selector}'"
        )

        self._element.send_keys(text_to_send)
        return self

    def clear(self) -> "ElementProxy":
        """Limpa o conteúdo de um campo de texto (input, textarea)."""
        self._find()  # Garante que _used_selector seja preenchido
        self._worker.logger.info(
            f"A limpar o conteúdo do elemento: '{self._used_selector}'"
        )
        self._element.clear()
        return self

    def find_nested_element(
        self, nested_selector: SelectorDefinition
    ) -> "ElementProxy":
        """
        Busca um elemento aninhado dentro deste elemento, retornando um novo ElementProxy.
        """
        self._worker.logger.debug(
            f"A criar proxy para elemento aninhado com seletor '{nested_selector.primary}'"
        )
        # O novo proxy recebe `self` como seu contexto de busca (pai).
        return ElementProxy(worker=self._worker, selector=nested_selector, parent=self)

    def __repr__(self) -> str:
        if self._used_selector:
            return f"<ElementProxy selector='{self._used_selector}' (resolved)>"
        return f"<ElementProxy selector='{self._selector.primary}' (unresolved)>"
