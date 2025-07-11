# Define um sistema de gestão de seletores com estratégias de fallback.
#
# Este módulo implementa o 'SelectorManager', uma classe que orquestra a
# localização de elementos na página usando diferentes estratégias, tornando
# a automação mais resiliente a pequenas mudanças no front-end.

from typing import List, Optional, Dict, Tuple, Union, cast

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..exceptions import ConfigurationError, ElementNotFoundError
from ..settings import Settings
from ..types import (
    LoggerProtocol,
    SelectorType,
    SelectorValue,
    TimeoutMs,
    WebDriverProtocol,
    WebElementProtocol,
)
from ..utils import validate_selector


class SelectorDefinition:
    """
    Representa a definição de um seletor de forma estruturada.

    Esta classe serve como um Objeto de Transferência de Dados (DTO) para
    agrupar todas as informações relacionadas a um seletor, como o seu valor
    primário, um possível fallback, o tipo e o tempo de espera.
    """

    def __init__(
        self,
        primary: SelectorValue,
        selector_type: SelectorType = SelectorType.XPATH,
        fallback: Optional[SelectorValue] = None,
        timeout_ms: Optional[
            TimeoutMs
        ] = None,  # Permitir None para usar o padrão global
    ):
        self.primary = validate_selector(primary)
        self.selector_type = selector_type
        self.fallback = validate_selector(fallback) if fallback else None
        self.timeout_ms = timeout_ms


def create_selector(
    primary: SelectorValue,
    selector_type: SelectorType = SelectorType.XPATH,
    fallback: Optional[SelectorValue] = None,
    timeout_ms: Optional[TimeoutMs] = None,
) -> SelectorDefinition:
    """
    Função 'factory' para criar instâncias de SelectorDefinition de forma conveniente.
    """
    return SelectorDefinition(
        primary=primary,
        selector_type=selector_type,
        fallback=fallback,
        timeout_ms=timeout_ms,
    )


# noinspection GrazieInspection
class SelectorManager:
    """
    Gere a lógica de encontrar elementos na página usando 'SelectorDefinitions'.

    Abstrai a complexidade do Selenium, adiciona lógicas de resiliência como
    fallback e fornece um logging claro sobre as operações de busca.
    """

    _SELECTOR_MAPPING: Dict[SelectorType, str] = {
        SelectorType.XPATH: By.XPATH,
        SelectorType.CSS: By.CSS_SELECTOR,
        SelectorType.ID: By.ID,
        SelectorType.NAME: By.NAME,
        SelectorType.CLASS_NAME: By.CLASS_NAME,
        SelectorType.TAG_NAME: By.TAG_NAME,
        SelectorType.LINK_TEXT: By.LINK_TEXT,
        SelectorType.PARTIAL_LINK_TEXT: By.PARTIAL_LINK_TEXT,
    }

    def __init__(self, logger: LoggerProtocol, settings: Settings):
        """
        Inicializa o gestor de seletores.

        Args:
            logger: A instância do logger para registrar as operações de busca.
            settings: As configurações globais para obter timeouts padrão.
        """
        self.logger = logger
        self.settings = settings
        self.default_timeout_ms = self.settings.get("timeouts", {}).get(
            "element_find_ms", 30_000
        )

    def find_element(
        self,
        driver_or_element: Union[WebDriverProtocol, WebElementProtocol],
        definition: SelectorDefinition,
    ) -> Tuple[WebElementProtocol, SelectorValue]:
        """
        Encontra um único elemento na página (ou dentro de outro elemento) usando a estratégia de fallback.

        Args:
            driver_or_element: A instância do WebDriver ou um WebElement de contexto para a busca.
            definition: O objeto 'SelectorDefinition' com os detalhes do seletor.

        Returns:
            Uma tupla contendo o elemento da web encontrado e o valor do seletor usado com sucesso.

        Raises:
            ElementNotFoundError: Se o elemento não for encontrado.
        """
        timeout = (
            definition.timeout_ms
            if definition.timeout_ms is not None
            else self.default_timeout_ms
        )
        self.logger.debug(
            f"A procurar elemento com seletor primário: '{definition.primary}' (Timeout: {timeout}ms)"
        )

        try:
            element = self._find_with_wait(
                driver_or_element, definition.primary, definition.selector_type, timeout
            )
            # Retorna o seletor usado
            return element, definition.primary
        except (NoSuchElementException, TimeoutException):
            self.logger.warning(
                f"Seletor primário '{definition.primary}' falhou. A tentar fallback, se disponível."
            )
            if definition.fallback:
                try:
                    element = self._find_with_wait(
                        driver_or_element,
                        definition.fallback,
                        definition.selector_type,
                        timeout,
                    )
                    self.logger.info(
                        f"Elemento encontrado com o seletor de fallback: '{definition.fallback}'"
                    )
                    # Retorna o seletor de fallback usado
                    return element, definition.fallback
                except (NoSuchElementException, TimeoutException) as fallback_error:
                    raise ElementNotFoundError(
                        "Elemento não encontrado com seletor primário nem com fallback.",
                        context={
                            "primary_selector": definition.primary,
                            "fallback_selector": definition.fallback,
                            "timeout_ms": timeout,
                        },
                        original_error=fallback_error,
                    )
            raise ElementNotFoundError(
                f"Elemento não encontrado com seletor: '{definition.primary}'",
                context={"selector": definition.primary, "timeout_ms": timeout},
            )

    def find_elements(
        self, driver: WebDriverProtocol, definition: SelectorDefinition
    ) -> List[WebElementProtocol]:
        """
        Encontra múltiplos elementos na página que correspondem a um seletor.
        """
        timeout = (
            definition.timeout_ms
            if definition.timeout_ms is not None
            else self.default_timeout_ms
        )
        self.logger.debug(
            f"A procurar múltiplos elementos com seletor: '{definition.primary}' (Timeout: {timeout}ms)"
        )
        by = self._get_selenium_by(definition.selector_type)
        try:
            wait = WebDriverWait(cast(WebDriver, driver), timeout / 1_000.0)
            return wait.until(
                EC.presence_of_all_elements_located((by, definition.primary))
            )
        except TimeoutException:
            self.logger.warning(
                f"Nenhum elemento encontrado para o seletor '{definition.primary}' dentro do timeout."
            )
            return []

    def _find_with_wait(
        self,
        context: Union[WebDriverProtocol, WebElementProtocol],
        selector: str,
        selector_type: SelectorType,
        timeout_ms: int,
    ) -> WebElementProtocol:
        # Método auxiliar privado que usa a espera explícita do Selenium.
        by = self._get_selenium_by(selector_type)
        # O contexto da espera agora é o driver ou um elemento pai
        wait = WebDriverWait(
            cast(Union[WebDriver, WebElement], context), timeout_ms / 1_000.0
        )
        # Usa um lambda para que 'find_element' seja chamado no contexto correto
        return wait.until(lambda d: d.find_element(by, selector))

    def _get_selenium_by(self, selector_type: SelectorType) -> str:
        # Mapeia o nosso Enum 'SelectorType' para o objeto 'By' do Selenium.
        by_value = self._SELECTOR_MAPPING.get(selector_type)
        if not by_value:
            raise ConfigurationError(
                f"Tipo de seletor desconhecido ou não suportado: {selector_type}"
            )
        return by_value
