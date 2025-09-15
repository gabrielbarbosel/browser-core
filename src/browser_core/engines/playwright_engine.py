from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..exceptions import WorkerError

try:  # Playwright pode não estar instalado em todos os ambientes
    from playwright.sync_api import (
        sync_playwright,
        Browser,
        BrowserContext,
        Page,
    )
except ImportError:  # pragma: no cover - dependência opcional
    sync_playwright = None  # type: ignore[assignment]
    Browser = BrowserContext = Page = Any  # type: ignore[misc]

if TYPE_CHECKING:  # Evita importação circular para o type checker
    from ..orchestration.worker import Worker


class PlaywrightEngine:
    """Implementação simples do AutomationEngine usando Playwright."""

    def __init__(self, worker: "Worker", config: dict) -> None:
        self._worker = worker
        self._config = config
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def start(self, profile_dir: Path) -> Page:
        """Inicia o navegador Playwright e retorna a página principal."""
        self._worker.logger.info("Iniciando PlaywrightEngine")
        self._playwright = sync_playwright().start()
        browser_key = self._worker.driver_info.get("name", "chromium").lower()
        if browser_key not in ("chromium", "firefox", "webkit"):
            browser_key = "chromium"
        browser_type = getattr(self._playwright, browser_key)
        self._browser = browser_type.launch(headless=self._config.get("headless", True))
        # Usa contexto persistente (no Playwright, via browser_type.launch_persistent_context)
        # para aproveitar diretórios de perfil como nos snapshots
        try:
            self._context = browser_type.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self._config.get("headless", True),
            )
            # Quando usamos persistent context, o browser retornado é acessível via _context.browser
            self._browser = self._context.browser  # type: ignore[attr-defined]
        except Exception:
            # Fallback para contexto não persistente caso a API não esteja disponível
            self._context = self._browser.new_context()
        self._page = self._context.new_page()
        return self._page

    def stop(self) -> None:
        """Fecha o navegador Playwright e limpa recursos."""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._worker.logger.info("PlaywrightEngine finalizado")

    def navigate_to(self, url: str) -> None:
        """Navega para a URL especificada usando a aba ativa."""
        if not self._page:
            raise WorkerError("Engine não iniciada")
        self._page.goto(url)

    def find_element(self, selector: Any) -> Any:
        """Localiza um elemento na página através do seletor informado."""
        if not self._page:
            raise WorkerError("Engine não iniciada")
        return self._page.query_selector(selector.primary)

    def execute_script(self, script: str, *args: Any) -> Any:
        """Executa JavaScript no contexto da página ativa."""
        if not self._page:
            raise WorkerError("Engine não iniciada")
        return self._page.evaluate(script, *args)
