print("--- LOADING LATEST BROWSER_AGENT.PY (v2) ---")
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from models.scenario import BrowserScenario, BrowserAction

from playwright_stealth import Stealth

class BrowserAgent:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright_context_manager = None
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self):
        """Start the Playwright browser with stealth."""
        self._playwright_context_manager = Stealth().use_async(async_playwright())
        self.playwright = await self._playwright_context_manager.__aenter__()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

    async def create_context(self) -> BrowserContext:
        """Create a new browser context with video recording enabled."""
        if not self.browser:
            await self.start()
        
        # Ensure media directories exist
        os.makedirs("media/videos", exist_ok=True)
        os.makedirs("media/screenshots", exist_ok=True)

        self.context = await self.browser.new_context(
            record_video_dir="./media/videos/",
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        # Stealth is now applied globally, no need to apply it per page
        return self.context

    async def stop(self):
        """Stop the browser and close context."""
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass # Ignore errors if context is already closed
        if self.browser:
            await self.browser.close()
        if self._playwright_context_manager:
            await self._playwright_context_manager.__aexit__(None, None, None)
        
        self.context = None
        self.browser = None
        self.playwright = None
        self._playwright_context_manager = None

    async def execute_step(self, step: BrowserAction) -> str:
        """Execute a single step of the scenario."""
        if not self.page:
            raise RuntimeError("Browser page is not initialized. Call create_context() first.")

        try:
            if step.action_type == "goto":
                await self.page.goto(step.value)
            elif step.action_type == "click":
                await self.page.click(step.selector)
            elif step.action_type == "fill":
                await self.page.fill(step.selector, step.value)
            elif step.action_type == "screenshot":
                # Explicit screenshot step
                pass # Handled automatically after every step or explicitly here if needed
            elif step.action_type == "wait":
                 await self.page.wait_for_timeout(int(step.value))
            else:
                print(f"Unknown action type: {step.action_type}")
            
            # Always take a screenshot after action for verification/visualization
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            screenshot_path = f"media/screenshots/{timestamp}_{step.action_type}.png"
            await self.page.screenshot(path=screenshot_path)
            
            return f"Executed {step.action_type}: {step.description}"

        except Exception as e:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            error_screenshot_path = f"media/screenshots/{timestamp}_error.png"
            await self.page.screenshot(path=error_screenshot_path)
            return f"Error executing {step.action_type}: {str(e)}"

    async def execute_scenario(self, scenario: BrowserScenario) -> Dict[str, Any]:
        """Execute the entire scenario."""
        results = []
        video_path = None
        if not self.context:
            await self.create_context()
        
        try:
            for step in scenario.steps:
                result = await self.execute_step(step)
                results.append(result)
                # Small pause to ensure video captures the state
                await asyncio.sleep(0.5) 
        finally:
            # The context will be closed by the stop() method later.
            # We just need to get the path to the video.
            if self.page and self.page.video:
                 video_path = await self.page.video.path()
            
        return {
            "results": results,
            "video_path": video_path
        }
