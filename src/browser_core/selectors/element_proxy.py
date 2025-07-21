# Define a classe ElementProxy para interações fluentes com elementos da web.

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional, cast

from selenium.webdriver import ActionChains
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .manager import SelectorDefinition
from ..exceptions import ElementActionError
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
        self.worker = worker
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
                self._parent._find() if self._parent else self.worker.driver
            )

            #  A busca é feita pelo SelectorManager, que retorna o elemento e o seletor usado
            self.worker.logger.debug(
                f"ElementProxy: A procurar elemento com seletor '{self._selector.primary}'..."
            )
            self._element, self._used_selector = (
                self.worker.selector_manager.find_element(
                    search_context, self._selector
                )
            )
            self.worker.logger.debug(
                f"ElementProxy: Elemento encontrado com '{self._used_selector}' e cacheado."
            )

        return self._element

    @property
    def text(self) -> _ValueProxy:
        """Retorna o conteúdo de texto visível do elemento."""
        return _ValueProxy(lambda: self._find().text, self.worker)

    @property
    def tag_name(self) -> str:
        """Retorna o nome da tag do elemento."""
        return self._find().tag_name

    def get_attribute(self, name: str) -> str:
        """Retorna o valor de um atributo do elemento."""
        return self._find().get_attribute(name)

    def click(self) -> "ElementProxy":
        """Executa a ação de clique no elemento."""
        element = self._find()  # Garante que _used_selector seja preenchido
        self._wait_actionable()
        self.worker.logger.info(
            f"A clicar no elemento definido por: '{self._used_selector}'"
        )
        element.click()
        return self

    # --- Propriedades de estado ---

    def is_displayed(self) -> bool:
        """Indica se o elemento está visível na página."""
        return self._find().is_displayed()

    def is_enabled(self) -> bool:
        """Indica se o elemento está habilitado para interação."""
        return self._find().is_enabled()

    def is_selected(self) -> bool:
        """Indica se o elemento está selecionado."""
        return self._find().is_selected()

    # --- Ações adicionais ---

    def hover(self) -> "ElementProxy":
        """Move o cursor para cima do elemento."""
        element = self._find()
        ActionChains(self.worker.driver).move_to_element(
            cast(WebElement, element)
        ).perform()
        return self

    def scroll_to_view(self) -> "ElementProxy":
        """Rola a página para que o elemento fique visível."""
        element = self._find()
        self.worker.execute_script("arguments[0].scrollIntoView(true);", element)
        return self

    def get_parent(self) -> "ElementProxy":
        """Retorna o ElementProxy do elemento pai."""
        parent_selector = SelectorDefinition(
            "..", selector_type=self._selector.selector_type
        )
        return ElementProxy(worker=self.worker, selector=parent_selector, parent=self)

    def send_keys(self, *values: str) -> "ElementProxy":
        """
        Simula a digitação de texto no elemento, mascarando dados sensíveis no log.
        """
        text_to_send = "".join(values)
        masked_text = mask_sensitive_data(text_to_send)

        element = self._find()
        self._wait_actionable()
        self.worker.logger.info(
            f"A enviar texto '{masked_text}' para o elemento: '{self._used_selector}'"
        )

        element.send_keys(text_to_send)
        return self

    def clear(self) -> "ElementProxy":
        """Limpa o conteúdo de um campo de texto (input, textarea)."""
        element = self._find()
        self._wait_actionable()
        self.worker.logger.info(
            f"A limpar o conteúdo do elemento: '{self._used_selector}'"
        )
        element.clear()
        return self

    def _wait_actionable(self) -> None:
        timeout = self.worker.settings.get("timeouts", {}).get(
            "element_action_ms", 5000
        )
        try:
            WebDriverWait(self.worker.driver, timeout / 1000.0).until(
                lambda d: self._element.is_displayed() and self._element.is_enabled()
            )
        except Exception as exc:
            raise ElementActionError(
                "Elemento não está acionável para interação",
                context={"selector": self._used_selector, "timeout_ms": timeout},
                original_error=exc,
            )

    def find_nested_element(
        self, nested_selector: SelectorDefinition
    ) -> "ElementProxy":
        """
        Busca um elemento aninhado dentro deste elemento, retornando um novo ElementProxy.
        """
        self.worker.logger.debug(
            f"A criar proxy para elemento aninhado com seletor '{nested_selector.primary}'"
        )
        # O novo proxy recebe `self` como seu contexto de busca (pai).
        return ElementProxy(worker=self.worker, selector=nested_selector, parent=self)

    # --- Métodos de espera ---

    def wait_for_clickable(self, timeout_ms: int) -> "ElementProxy":
        """Aguarda até que o elemento esteja clicável."""
        element = self._find()
        WebDriverWait(self.worker.driver, timeout_ms / 1_000).until(
            EC.element_to_be_clickable(cast(WebElement, element))
        )
        return self

    def wait_for_visible(self, timeout_ms: int) -> "ElementProxy":
        """Aguarda até que o elemento esteja visível."""
        element = self._find()
        WebDriverWait(self.worker.driver, timeout_ms / 1_000).until(
            EC.visibility_of(cast(WebElement, element))
        )
        return self

    def wait_for_disappear(self, timeout_ms: int) -> "ElementProxy":
        """Aguarda o elemento desaparecer da página."""
        element = self._find()
        WebDriverWait(self.worker.driver, timeout_ms / 1_000).until_not(
            lambda d: element.is_displayed()
        )
        return self

    def __repr__(self) -> str:
        if self._used_selector:
            return f"<ElementProxy selector='{self._used_selector}' (resolved)>"
        return f"<ElementProxy selector='{self._selector.primary}' (unresolved)>"


class _ValueProxy:
    def __init__(self, getter, worker: "Worker"):
        self._getter = getter
        self.worker = worker

    def __str__(self) -> str:
        return self._getter()

    def get(self) -> str:
        return self._getter()

    def should_be(self, expected: str, timeout_ms: Optional[int] = None) -> None:
        timeout = (
            timeout_ms
            if timeout_ms is not None
            else self.worker.settings.get("timeouts", {}).get("assertion_ms", 5000)
        )
        end = time.time() + timeout / 1000.0
        last = self.get()
        while time.time() < end:
            if last == expected:
                return
            time.sleep(0.5)
            last = self.get()
        raise AssertionError(f"Esperado '{expected}', obtido '{last}'")
