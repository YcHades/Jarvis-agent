import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.config import get_default_profile, load_browser_use_config
from browser_use.controller.service import Controller
from browser_use.filesystem.file_system import FileSystem

class BrowserUseLight:

    def __init__(self):
        self.config = load_browser_use_config()
        self.browser_session: BrowserSession | None = None
        self.controller: Controller | None = None
        self.file_system: FileSystem | None = None

    async def _init_browser_session(self, **kwargs):
        """Initialize browser session using config"""
        if self.browser_session:
            return

        # Get profile config
        # profile_config = get_default_profile(self.config)

        # Merge profile config with defaults and overrides
        profile_data = {
            'downloads_path': str(Path.home() / 'downloads'),
            'wait_between_actions': 0.5,
            'keep_alive': True,
            'user_data_dir': '~/.config/browseruse/profiles/default',
            'is_mobile': False,
            'device_scale_factor': 1.0,
            'disable_security': False,
            'headless': True,
            "id": "79bfe7fd-1a9b-4c69-a7aa-0266ff82e49b",
            "default": True,
            "created_at": "2025-07-16T10:12:15.367877",
            "allowed_domains": None,
            # **profile_config,  # Config values override defaults
        }

        # Merge any additional kwargs that are valid BrowserProfile fields
        for key, value in kwargs.items():
            profile_data[key] = value

        # Create browser profile
        profile = BrowserProfile(**profile_data)

        # Create browser session
        self.browser_session = BrowserSession(browser_profile=profile)
        await self.browser_session.start()

        # Create controller for direct actions
        self.controller = Controller()

        # Initialize FileSystem for extraction actions
        file_system_path = profile_data.get('file_system_path', '~/.browser-use-mcp')
        self.file_system = FileSystem(base_dir=Path(file_system_path).expanduser())

    async def _navigate(self, url: str, new_tab: bool = False) -> str:
        """Navigate to a URL."""
        if not self.browser_session:
            return 'Error: No browser session active'

        if new_tab:
            page = await self.browser_session.navigate(url, new_tab=True)
            tab_idx = self.browser_session.tabs.index(page)
            return f'Opened new tab #{tab_idx} with URL: {url}'
        else:
            await self.browser_session.navigate(url)
            return f'Navigated to: {url}'

    async def _click(self, index: int, new_tab: bool = False) -> str:
        """Click an element by index."""
        if not self.browser_session:
            return 'Error: No browser session active'

        # Get the element
        element = await self.browser_session.get_dom_element_by_index(index)
        if not element:
            return f'Element with index {index} not found'

        if new_tab:
            # For links, extract href and open in new tab
            href = element.attributes.get('href')
            if href:
                # Convert relative href to absolute URL
                current_page = await self.browser_session.get_current_page()
                if href.startswith('/'):
                    # Relative URL - construct full URL
                    from urllib.parse import urlparse

                    parsed = urlparse(current_page.url)
                    full_url = f'{parsed.scheme}://{parsed.netloc}{href}'
                else:
                    full_url = href

                # Open link in new tab
                page = await self.browser_session.navigate(full_url, new_tab=True)
                tab_idx = self.browser_session.tabs.index(page)
                return f'Clicked element {index} and opened in new tab #{tab_idx}'
            else:
                # For non-link elements, try Cmd/Ctrl+Click
                page = await self.browser_session.get_current_page()
                element_handle = await self.browser_session.get_locate_element(element)
                if element_handle:
                    # Use playwright's click with modifiers
                    modifier: Literal['Meta', 'Control'] = 'Meta' if sys.platform == 'darwin' else 'Control'
                    await element_handle.click(modifiers=[modifier])
                    # Wait a bit for potential new tab
                    await asyncio.sleep(0.5)
                    return f'Clicked element {index} with {modifier} key (new tab if supported)'
                else:
                    return f'Could not locate element {index} for modified click'
        else:
            # Normal click
            await self.browser_session._click_element_node(element)
            return f'Clicked element {index}'

    async def _get_browser_state(self, include_screenshot: bool = False) -> str:
        """Get current browser state."""
        if not self.browser_session:
            return 'Error: No browser session active'

        state = await self.browser_session.get_state_summary(cache_clickable_elements_hashes=False)

        result = {
            'url': state.url,
            'title': state.title,
            'tabs': [{'url': tab.url, 'title': tab.title} for tab in state.tabs],
            'interactive_elements': [],
        }

        # Add interactive elements with their indices
        for index, element in state.selector_map.items():
            elem_info = {
                'index': index,
                'tag': element.tag_name,
                'text': element.get_all_text_till_next_clickable_element(max_depth=2)[:100],
            }
            if element.attributes.get('placeholder'):
                elem_info['placeholder'] = element.attributes['placeholder']
            if element.attributes.get('href'):
                elem_info['href'] = element.attributes['href']
            result['interactive_elements'].append(elem_info)

        if include_screenshot and state.screenshot:
            result['screenshot'] = state.screenshot

        return "============== BROWSER STATE BEGIN ==============\n" + json.dumps(result, indent=2, ensure_ascii=False) + "\n============== BROWSER STATE END =============="

    async def _type_text(self, index: int, text: str) -> str:
        """Type text into an element."""
        if not self.browser_session:
            return 'Error: No browser session active'

        element = await self.browser_session.get_dom_element_by_index(index)
        if not element:
            return f'Element with index {index} not found'

        await self.browser_session._input_text_element_node(element, text)
        return f"Typed '{text}' into element {index}"

    async def _send_keys(self, keys: str) -> str:
        if not self.browser_session:
            return 'Error: No browser session active'

        page = await self.browser_session.get_current_page()
        await page.keyboard.press(keys)
        return f"Sent keys: {keys}"

    async def _go_back(self) -> str:
        """Go back in browser history."""
        if not self.browser_session:
            return 'Error: No browser session active'

        await self.browser_session.go_back()
        return 'Navigated back'

    async def _close_browser(self) -> str:
        """Close the browser session."""
        if self.browser_session:
            await self.browser_session.stop()
            self.browser_session = None
            self.controller = None
            return 'Browser closed'
        return 'No browser session to close'

    async def _list_tabs(self) -> str:
        """List all open tabs."""
        if not self.browser_session:
            return 'Error: No browser session active'

        tabs = []
        for i, tab in enumerate(self.browser_session.tabs):
            tabs.append({'index': i, 'url': tab.url, 'title': await tab.title() if not tab.is_closed() else 'Closed'})
        return json.dumps(tabs, indent=2)

    async def _switch_tab(self, tab_index: int) -> str:
        """Switch to a different tab."""
        if not self.browser_session:
            return 'Error: No browser session active'

        await self.browser_session.switch_to_tab(tab_index)
        page = await self.browser_session.get_current_page()
        return f'Switched to tab {tab_index}: {page.url}'

    async def _close_tab(self, tab_index: int) -> str:
        """Close a specific tab."""
        if not self.browser_session:
            return 'Error: No browser session active'

        if 0 <= tab_index < len(self.browser_session.tabs):
            tab = self.browser_session.tabs[tab_index]
            url = tab.url
            await tab.close()
            return f'Closed tab {tab_index}: {url}'
        return f'Invalid tab index: {tab_index}'

