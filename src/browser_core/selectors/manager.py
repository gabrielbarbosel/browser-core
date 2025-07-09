# Define um sistema de gestão de seletores com estratégias de fallback.
#
# Este módulo implementa o `SelectorManager`, uma classe que orquestra a
# localização de elementos na página usando diferentes estratégias, tornando
# a automação mais resiliente a pequenas mudanças no front-end.

from typing import Any, List, Optional

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..exceptions import ConfigurationError, ElementNotFoundError
from ..types import LoggerProtocol, SelectorType, SelectorValue, TimeoutMs, WebDriverProtocol
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
            timeout_ms: TimeoutMs = 30000,
    ):
        self.primary = validate_selector(primary)
        self.selector_type = selector_type
        self.fallback = validate_selector(fallback) if fallback else None
        self.timeout_ms = timeout_ms


def create_selector(
        primary: SelectorValue,
        selector_type: SelectorType = SelectorType.XPATH,
        fallback: Optional[SelectorValue] = None,
        timeout_ms: TimeoutMs = 30000
) -> SelectorDefinition:
    """
    Função 'factory' para criar instâncias de SelectorDefinition de forma conveniente.
    """
    return SelectorDefinition(
        primary=primary,
        selector_type=selector_type,
        fallback=fallback,
        timeout_ms=timeout_ms
    )


class SelectorManager:
    """
    Gere a lógica de encontrar elementos na página usando 'SelectorDefinitions'.

    Abstrai a complexidade do Selenium, adiciona lógicas de resiliência como
    fallback e fornece um logging claro sobre as operações de busca.
    """

    def __init__(self, logger: LoggerProtocol):
        """
        Inicializa o gestor de seletores.

        Args:
            logger: A instância do logger para registar as operações de busca.
        """
        self.logger = logger

    def find_element(self, driver: WebDriverProtocol, definition: SelectorDefinition) -> Any:
        """
        Encontra um único elemento na página usando a estratégia de fallback.

        Args:
            driver: A instância do WebDriver para interagir com o navegador.
            definition: O objeto `SelectorDefinition` com os detalhes do seletor.

        Returns:
            O elemento da web encontrado.

        Raises:
            ElementNotFoundError: Se o elemento não for encontrado com o seletor
                                  primário nem com o de fallback.
        """
        self.logger.debug(f"A procurar elemento com seletor primário: '{definition.primary}'")
        try:
            return self._find_with_wait(
                driver, definition.primary, definition.selector_type, definition.timeout_ms
            )
        except (NoSuchElementException, TimeoutException):
            self.logger.warning(
                f"Seletor primário '{definition.primary}' falhou. A tentar fallback, se disponível."
            )
            if definition.fallback:
                try:
                    element = self._find_with_wait(
                        driver, definition.fallback, definition.selector_type, definition.timeout_ms
                    )
                    self.logger.info(f"Elemento encontrado com o seletor de fallback: '{definition.fallback}'")
                    return element
                except (NoSuchElementException, TimeoutException) as fallback_error:
                    raise ElementNotFoundError(
                        "Elemento não encontrado com seletor primário nem com fallback.",
                        context={
                            "primary_selector": definition.primary,
                            "fallback_selector": definition.fallback,
                            "timeout_ms": definition.timeout_ms
                        },
                        original_error=fallback_error,
                    )
            raise ElementNotFoundError(
                f"Elemento não encontrado com seletor: '{definition.primary}'",
                context={
                    "selector": definition.primary,
                    "timeout_ms": definition.timeout_ms
                },
            )

    def find_elements(self, driver: WebDriverProtocol, definition: SelectorDefinition) -> List[Any]:
        """
        Encontra múltiplos elementos na página que correspondem a um seletor.

        Args:
            driver: A instância do WebDriver.
            definition: A definição do seletor a ser usado.

        Returns:
            Uma lista de elementos da web. A lista estará vazia se nenhum for encontrado.
        """
        self.logger.debug(f"A procurar múltiplos elementos com seletor: '{definition.primary}'")
        by = self._get_selenium_by(definition.selector_type)
        try:
            # Espera que pelo menos um elemento esteja presente para evitar retornos vazios.
            WebDriverWait(driver, definition.timeout_ms / 1000.0).until(
                EC.presence_of_all_elements_located((by, definition.primary))
            )
            return driver.find_elements(by, definition.primary)
        except TimeoutException:
            self.logger.warning(f"Nenhum elemento encontrado para o seletor '{definition.primary}' dentro do timeout.")
            return []

    def _find_with_wait(
            self, driver: WebDriverProtocol, selector: str, selector_type: SelectorType, timeout_ms: int
    ) -> Any:
        # Método auxiliar privado que usa a espera explícita do Selenium.
        by = self._get_selenium_by(selector_type)
        wait = WebDriverWait(driver, timeout_ms / 1000.0)
        return wait.until(EC.presence_of_element_located((by, selector)))

    @staticmethod
    def _get_selenium_by(selector_type: SelectorType) -> By:
        # Mapeia o nosso Enum `SelectorType` para o objeto `By` do Selenium.
        mapping = {
            SelectorType.XPATH: By.XPATH,
            SelectorType.CSS: By.CSS_SELECTOR,
            SelectorType.ID: By.ID,
            SelectorType.NAME: By.NAME,
            SelectorType.CLASS_NAME: By.CLASS_NAME,
            SelectorType.TAG_NAME: By.TAG_NAME,
            SelectorType.LINK_TEXT: By.LINK_TEXT,
            SelectorType.PARTIAL_LINK_TEXT: By.PARTIAL_LINK_TEXT,
        }
        by_value = mapping.get(selector_type)
        if not by_value:
            raise ConfigurationError(f"Tipo de seletor desconhecido ou não suportado: {selector_type}")
        return by_value
