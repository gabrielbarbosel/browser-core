# Define as exceções personalizadas para o framework browser-core.
#
# Este módulo estabelece uma hierarquia de classes de erro que permitem
# um tratamento de falhas específico e contextualizado para diferentes
# cenários da automação de navegadores.

from typing import Any, Dict, Optional


class BrowserCoreError(Exception):
    """
    Exceção base para todos os erros gerados pelo browser-core.
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
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Contexto: {context_str})"
        if self.original_error:
            return f"{self.message} | Erro Original: {self.original_error}"
        return self.message


class StorageEngineError(BrowserCoreError):
    """Lançada para qualquer falha dentro do StorageEngine (ex: IO, hash)."""
    pass


class SnapshotError(BrowserCoreError):
    """Lançada para falhas no SnapshotManager (ex: snapshot não encontrado, falha na materialização)."""
    pass


class WorkerError(BrowserCoreError):
    """Lançada para erros relacionados ao ciclo de vida de um Worker (ex: falha ao iniciar/parar)."""
    pass


class DriverError(BrowserCoreError):
    """Lançada para erros relacionados especificamente ao WebDriver (ex: falha no download ou inicialização)."""
    pass


class ConfigurationError(BrowserCoreError):
    """Lançada quando uma configuração fornecida é inválida, ausente ou mal formatada."""
    pass


# --- Exceções de Operações do Navegador (Usadas pelo Worker) ---

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
