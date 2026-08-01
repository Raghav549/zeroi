import logging
from typing import Any

from ..config import settings
from ..errors import ExecutionError

log = logging.getLogger(__name__)


class BrowserAgent:
    def __init__(self) -> None:
        self.playwright = None
        self.browser = None
        self.contexts: dict[str, Any] = {}

    async def ensure_browser(self) -> None:
        if self.browser:
            return

        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            raise ExecutionError("playwright not installed") from exc

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=settings.browser_headless)

    async def get_context(self, session_id: str):
        await self.ensure_browser()
        if session_id not in self.contexts:
            self.contexts[session_id] = await self.browser.new_context()
        return self.contexts[session_id]

    async def execute_flow(self, session_id: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
        context = await self.get_context(session_id)
        page = context.pages[0] if context.pages else await context.new_page()
        results: list[dict[str, Any]] = []
        extracted: dict[str, Any] = {}

        for action in actions:
            kind = action.get("type")

            if kind == "goto":
                await page.goto(action["url"], timeout=60000)
                results.append({"type": "goto", "url": action["url"], "ok": True})

            elif kind == "click":
                await page.click(action["selector"], timeout=30000)
                results.append({"type": "click", "selector": action["selector"], "ok": True})

            elif kind == "fill":
                await page.fill(action["selector"], action["value"], timeout=30000)
                results.append({"type": "fill", "selector": action["selector"], "ok": True})

            elif kind == "press":
                await page.press(action.get("selector", "body"), action["key"])
                results.append({"type": "press", "key": action["key"], "ok": True})

            elif kind == "extract":
                if action.get("selector"):
                    elements = await page.query_selector_all(action["selector"])
                    values = [await el.inner_text() for el in elements]
                    extracted[action.get("as", "extracted")] = values
                else:
                    extracted[action.get("as", "html")] = await page.content()
                results.append({"type": "extract", "ok": True})

            elif kind == "screenshot":
                extracted["screenshot"] = await page.screenshot()
                results.append({"type": "screenshot", "ok": True})

            else:
                raise ExecutionError(f"unsupported browser action: {kind}")

        return {"results": results, "extracted": extracted, "url": page.url}

    async def close(self) -> None:
        for ctx in self.contexts.values():
            await ctx.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
