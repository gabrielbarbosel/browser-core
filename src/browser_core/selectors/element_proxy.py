# Define a classe ElementProxy para interações fluentes com elementos da web.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .manager import SelectorDefinition
from ..utils import mask_sensitive_data  # <-- IMPORTAÇÃO ADICIONADA

# Evita importação circular, mantendo o type-hinting para a classe Worker.
if TYPE_CHECKING:
    from ..worker import Worker


class ElementProxy:
    """
    Representa um elemento da página de forma "preguiçosa" (lazy).

    A busca pelo elemento real no navegador só é realizada quando uma ação
    (como .click() ou .text) é invocada, permitindo uma API mais fluida.
    """

    def __init__(self, worker: "Worker", selector: SelectorDefinition):
        """
        Inicializa o proxy do elemento.

        Args:
            worker: A instância do Worker que irá executar as ações.
            selector: A definição do seletor para encontrar o elemento.
        """
        self._worker = worker
        self._selector = selector
        self._element: Any = None  # Cache para o WebElement, uma vez encontrado.

    def _find(self) -> Any:
        """
        Garante que o elemento foi encontrado e o retorna.
        """
        if self._element is None:
            self._worker.logger.debug(f"ElementProxy: A procurar elemento com seletor '{self._selector.primary}'...")
            self._element = self._worker.find_element(self._selector)
            self._worker.logger.debug("ElementProxy: Elemento encontrado e cacheado.")
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
        self._worker.logger.info(f"A clicar no elemento definido por: '{self._selector.primary}'")
        self._find().click()
        return self

    def send_keys(self, *values: str) -> "ElementProxy":
        """
        Simula a digitação de texto no elemento, mascarando dados sensíveis no log.
        """
        # Une os valores para processamento
        text_to_send = "".join(values)
        # Mascara a string ANTES de enviar para o log para segurança
        masked_text = mask_sensitive_data(text_to_send)

        self._worker.logger.info(f"A enviar texto '{masked_text}' para o elemento: '{self._selector.primary}'")

        # Envia o texto original (não mascarado) para o elemento
        self._find().send_keys(text_to_send)
        return self

    def clear(self) -> "ElementProxy":
        """Limpa o conteúdo de um campo de texto (input, textarea)."""
        self._worker.logger.info(f"A limpar o conteúdo do elemento: '{self._selector.primary}'")
        self._find().clear()
        return self

    def find_nested_element(self, nested_selector: SelectorDefinition) -> "ElementProxy":
        """
        Busca um elemento aninhado dentro deste elemento.
        """
        self._worker.logger.warning("Busca aninhada ainda não otimizada. A busca será feita no DOM global.")
        return self._worker.get(nested_selector)

    def __repr__(self) -> str:
        return f"<ElementProxy selector='{self._selector.primary}' type='{self._selector.selector_type.value}'>"
