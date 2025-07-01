# Define as exceções personalizadas para o framework browser-core.
#
# Este módulo estabelece uma hierarquia de classes de erro que permitem
# um tratamento de falhas específico e contextualizado para diferentes
# cenários da automação de navegadores.

from typing import Any, Dict, Optional


class BrowserCoreError(Exception):
    """
    Exceção base para todos os erros gerados pelo browser-core.

    Esta classe centraliza a lógica de carregar informações de contexto
    em cada erro, facilitando o rastreamento e a depuração de problemas.

    Attributes:
        message (str): A mensagem de erro principal.
        context (dict): Um dicionário com dados contextuais sobre o erro.
        original_error (Exception): A exceção original que foi capturada.
    """

    def __init__(
            self,
            message: str,
            context: Optional[Dict[str, Any]] = None,
            original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.original_error = original_error

    def __str__(self) -> str:
        # Formata a mensagem de erro para incluir o contexto, facilitando a leitura nos logs.
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Contexto: {context_str})"
        return self.message


class BrowserManagementError(BrowserCoreError):
    """Lançada quando falhas ocorrem na inicialização, configuração ou finalização do navegador."""
    pass


class ElementNotFoundError(BrowserCoreError):
    """Lançada quando um elemento esperado não é encontrado na página."""

    def __init__(
            self,
            message: str,
            selector: Optional[str] = None,
            timeout_ms: Optional[int] = None,
            **kwargs: Any,
    ):
        context = kwargs.get("context", {})
        if selector:
            context["selector"] = selector
        if timeout_ms:
            context["timeout_ms"] = timeout_ms
        super().__init__(message, context, kwargs.get("original_error"))


class ElementActionError(BrowserCoreError):
    """Lançada quando uma ação num elemento falha (ex: click, send_keys)."""
    pass


class PageLoadError(BrowserCoreError):
    """Lançada quando uma página ou URL falha ao carregar corretamente."""
    pass


class SessionStateError(BrowserCoreError):
    """Lançada quando ocorrem falhas em operações de estado da sessão (ex: salvar snapshot)."""
    pass


class DriverError(BrowserCoreError):
    """Lançada para erros relacionados especificamente ao WebDriver (ex: falha na instalação)."""
    pass


class ConfigurationError(BrowserCoreError):
    """Lançada quando uma configuração fornecida é inválida, ausente ou mal formatada."""
    pass


class ProfileError(BrowserCoreError):
    """Lançada para erros relacionados com a gestão de perfis de utilizador."""
    pass


class SnapshotError(BrowserCoreError):
    """Lançada quando uma falha ocorre durante a captura de um snapshot."""
    pass
