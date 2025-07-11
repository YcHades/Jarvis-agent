
import atexit
import base64
import io
import json
import logging
import multiprocessing
import time
import uuid
import signal
import threading
from typing import Callable, Any
from types import FrameType
from uuid import UUID, uuid4
from PIL import Image

import browsergym.core  # noqa F401 (we register the openended task as a gym environment)
import gymnasium as gym
import html2text
import numpy as np
import tenacity
from tenacity import RetryCallState
from tenacity.stop import stop_base
from browsergym.utils.obs import flatten_dom_to_str, overlay_som, flatten_axtree_to_str
from uvicorn.server import HANDLED_SIGNALS


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('jarvis_browser')

_should_exit = None
_shutdown_listeners: dict[UUID, Callable] = {}


def _register_signal_handler(sig: signal.Signals) -> None:
    original_handler = None

    def handler(sig_: int, frame: FrameType | None) -> None:
        logger.debug(f'shutdown_signal:{sig_}')
        global _should_exit
        if not _should_exit:
            _should_exit = True
            listeners = list(_shutdown_listeners.values())
            for callable in listeners:
                try:
                    callable()
                except Exception:
                    logger.exception('Error calling shutdown listener')
            if original_handler:
                original_handler(sig_, frame)  # type: ignore[unreachable]

    original_handler = signal.signal(sig, handler)

def _register_signal_handlers() -> None:
    global _should_exit
    if _should_exit is not None:
        return
    _should_exit = False

    logger.debug('_register_signal_handlers')

    # Check if we're in the main thread of the main interpreter
    if threading.current_thread() is threading.main_thread():
        logger.debug('_register_signal_handlers:main_thread')
        for sig in HANDLED_SIGNALS:
            _register_signal_handler(sig)
    else:
        logger.debug('_register_signal_handlers:not_main_thread')

def should_exit() -> bool:
    _register_signal_handlers()
    return bool(_should_exit)


def should_continue() -> bool:
    _register_signal_handlers()
    return not _should_exit

class stop_if_should_exit(stop_base):
    """Stop if the should_exit flag is set."""

    def __call__(self, retry_state: 'RetryCallState') -> bool:
        return bool(should_exit())

class BrowserInitException(Exception):
    def __init__(
        self, message: str = 'Failed to initialize browser environment'
    ) -> None:
        super().__init__(message)

def image_to_png_base64_url(
    image: np.ndarray | Image.Image, add_data_prefix: bool = False
) -> str:
    """Convert a numpy array to a base64 encoded png image url."""
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    if image.mode in ('RGBA', 'LA'):
        image = image.convert('RGB')
    buffered = io.BytesIO()
    image.save(buffered, format='PNG')

    image_base64 = base64.b64encode(buffered.getvalue()).decode()
    return (
        f'data:image/png;base64,{image_base64}'
        if add_data_prefix
        else f'{image_base64}'
    )


BROWSER_EVAL_GET_GOAL_ACTION = 'GET_EVAL_GOAL'
BROWSER_EVAL_GET_REWARDS_ACTION = 'GET_EVAL_REWARDS'


class BrowserEnv:
    def __init__(self, browsergym_eval_env: str | None = None):
        self.html_text_converter = self.get_html_text_converter()
        # self.eval_mode = False
        # self.eval_dir = ''

        # EVAL only: browsergym_eval_env must be provided for evaluation
        # self.browsergym_eval_env = browsergym_eval_env
        # self.eval_mode = bool(browsergym_eval_env)

        # Initialize browser environment process
        multiprocessing.set_start_method('spawn', force=True)
        self.browser_side, self.agent_side = multiprocessing.Pipe()

        self.init_browser()
        atexit.register(self.close)

    def get_html_text_converter(self) -> html2text.HTML2Text:
        html_text_converter = html2text.HTML2Text()
        # ignore links and images
        html_text_converter.ignore_links = False
        html_text_converter.ignore_images = True
        # use alt text for images
        html_text_converter.images_to_alt = True
        # disable auto text wrapping
        html_text_converter.body_width = 0
        return html_text_converter

    @tenacity.retry(
        wait=tenacity.wait_fixed(1),
        stop=tenacity.stop_after_attempt(5) | stop_if_should_exit(),
        retry=tenacity.retry_if_exception_type(BrowserInitException),
    )
    def init_browser(self) -> None:
        logger.debug('Starting browser env...')
        try:
            self.process = multiprocessing.Process(target=self.browser_process)
            self.process.start()
        except Exception as e:
            logger.error(f'Failed to start browser process: {e}')
            raise

        if not self.check_alive(timeout=200):
            self.close()
            raise BrowserInitException('Failed to start browser environment.')

    def browser_process(self) -> None:
        env = gym.make(
            'browsergym/openended',
            task_kwargs={'start_url': 'about:blank', 'goal': 'PLACEHOLDER_GOAL'},
            wait_for_user_message=False,
            headless=True,
            disable_env_checker=True,
            tags_to_mark='all',
            timeout=100000,
            pw_context_kwargs={'accept_downloads': True},
            pw_chromium_kwargs={'downloads_path': '/workspace/.downloads/'},
        )

        obs, info = env.reset()

        logger.info('Successfully called env.reset')
        logger.info('Browser env started.')

        while should_continue():
            try:
                if self.browser_side.poll(timeout=0.01):
                    unique_request_id, action_data = self.browser_side.recv()

                    # shutdown the browser environment
                    if unique_request_id == 'SHUTDOWN':
                        logger.debug('SHUTDOWN recv, shutting down browser env...')
                        env.close()
                        return
                    elif unique_request_id == 'IS_ALIVE':
                        self.browser_side.send(('ALIVE', None))
                        continue

                    action = action_data['action']
                    obs, reward, terminated, truncated, info = env.step(action)

                    # add text content of the page
                    html_str = flatten_dom_to_str(obs['dom_object'])
                    obs['text_content'] = self.html_text_converter.handle(html_str)
                    # make observation serializable
                    obs['set_of_marks'] = image_to_png_base64_url(
                        overlay_som(
                            obs['screenshot'], obs.get('extra_element_properties', {})
                        ),
                        add_data_prefix=True,
                    )
                    obs['screenshot'] = image_to_png_base64_url(
                        obs['screenshot'], add_data_prefix=True
                    )
                    obs['active_page_index'] = obs['active_page_index'].item()
                    obs['elapsed_time'] = obs['elapsed_time'].item()
                    self.browser_side.send((unique_request_id, obs))
            except KeyboardInterrupt:
                logger.debug('Browser env process interrupted by user.')
                try:
                    env.close()
                except Exception:
                    pass
                return

    def step(self, action_str: str, timeout: float = 120) -> dict:
        """Execute an action in the browser environment and return the observation."""
        unique_request_id = str(uuid.uuid4())
        self.agent_side.send((unique_request_id, {'action': action_str}))
        start_time = time.time()
        while True:
            if should_exit() or time.time() - start_time > timeout:
                raise TimeoutError('Browser environment took too long to respond.')
            if self.agent_side.poll(timeout=0.01):
                response_id, obs = self.agent_side.recv()
                if response_id == unique_request_id:
                    return dict(obs)

    def check_alive(self, timeout: float = 60) -> bool:
        self.agent_side.send(('IS_ALIVE', None))
        if self.agent_side.poll(timeout=timeout):
            response_id, _ = self.agent_side.recv()
            if response_id == 'ALIVE':
                return True
            logger.debug(f'Browser env is not alive. Response ID: {response_id}')
        return False

    def close(self) -> None:
        if not self.process.is_alive():
            return
        try:
            self.agent_side.send(('SHUTDOWN', None))
            self.process.join(5)  # Wait for the process to terminate
            if self.process.is_alive():
                logger.error(
                    'Browser process did not terminate, forcefully terminating...'
                )
                self.process.terminate()
                self.process.join(5)  # Wait for the process to terminate
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(5)  # Wait for the process to terminate
            self.agent_side.close()
            self.browser_side.close()
        except Exception as e:
            logger.error(f'Encountered an error when closing browser env: {e}')


def get_axtree_str(
    axtree_object: dict[str, Any],
    extra_element_properties: dict[str, Any],
    filter_visible_only: bool = False,
) -> str:
    cur_axtree_txt = flatten_axtree_to_str(
        axtree_object,
        extra_properties=extra_element_properties,
        with_clickable=True,
        skip_generic=False,
        filter_visible_only=filter_visible_only,
    )
    return str(cur_axtree_txt)

def get_agent_obs_text(obs: dict) -> str:
    text = f'[Current URL: {obs["url"]}]\n'
    text += f'[Focused element bid: {obs["focused_element_bid"]}]\n'

    text += '\n'

    if obs["error"]:
        text += (
            '================ BEGIN error message ===============\n'
            'The following error occurred when executing the last action:\n'
            f'{obs["last_browser_action_error"]}\n'
            '================ END error message ===============\n'
        )
    else:
        text += '[Action executed successfully.]\n'
    try:
        cur_axtree_txt = get_axtree_str(
            obs["axtree_object"],
            obs["extra_element_properties"]
        )
        text += (
            f'Accessibility tree of the COMPLETE webpage:\nNote: [bid] is the unique alpha-numeric identifier at the beginning of lines for each element in the AXTree. Always use bid to refer to elements in your actions.\n'
            f'============== BEGIN accessibility tree ==============\n'
            f'{cur_axtree_txt}\n'
            f'============== END accessibility tree ==============\n'
        )
    except Exception as e:
        text += f'\n[Error encountered when processing the accessibility tree: {e}]'
    return text

def refine_obs(obs: dict) -> dict:
    return {
        "content": obs['text_content'],
        "last_browser_action_error": obs.get('last_action_error', ''),
        "error": True if obs.get('last_action_error', '') else False,
        "focused_element_bid": obs.get('focused_element_bid', None),
        "axtree_object": obs.get('axtree_object', {}),
        "extra_element_properties": obs.get('extra_element_properties', {}),
        "url": obs.get('url', '')
    }

if __name__ == '__main__':
    browser = BrowserEnv()

    obs = refine_obs(
        browser.step("noop(10000)")
    )
    obs["content"] = get_agent_obs_text(obs)

    print(obs["content"])

    # with open("misc/test1.txt", "w", encoding="utf-8") as f:
    #     f.write(obs["content"])

    obs = refine_obs(
        browser.step("click('34')")
    )
    obs["content"] = get_agent_obs_text(obs)

    print(obs["content"])
    # with open("misc/test2.txt", "w", encoding="utf-8") as f:
    #     f.write(obs["content"])

    # obs = refine_obs(
    #     browser.step("fill('34', 'ychades150@gmail.com')")
    # )
    # obs["content"] = get_agent_obs_text(obs)
    # with open("misc/test3.txt", "w", encoding="utf-8") as f:
    #     f.write(obs["content"])

