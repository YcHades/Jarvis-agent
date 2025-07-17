import asyncio
import json

from browser_use import BrowserSession

from browser import BrowserUseLight


browser = BrowserUseLight()

async def browser_navigate( url: str, new_tab: bool = False):
    """
    跳转至指定 URL，支持新标签页打开。

    Args:
        url: 目标网页的 URL。
        new_tab: 是否在新标签页打开（默认 False）。
    """
    if browser.browser_session is None:
        await browser._init_browser_session()

    result = await browser._navigate(url, new_tab=new_tab)
    result_dict = {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }

    if new_tab:
        result_dict["instruction"] = "当前已处于新标签页下，不需要再进行进入新标签页的操作"

    yield result_dict

async def browser_click(index: int, new_tab: bool = False):
    """
    根据元素索引点击页面元素，支持新标签页打开链接。

    Args:
        index: 目标元素的索引号。
        new_tab: 是否通过新标签页打开（适用于链接，默认 False）。
    """
    result = await browser._click(index, new_tab=new_tab)
    result_dict = {
            "data": {
                "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
            },
            "instruction": ""
        }

    if new_tab:
        result_dict["instruction"] = "当前已处于新标签页下，不需要再进行进入新标签页的操作"

    yield result_dict

async def browser_get_browser_state():
    """
    获取当前浏览器的页面状态摘要
    """
    result = await browser._get_browser_state(include_screenshot=False)

    yield {
        "data": {
            "stream_chunk": result
        },
        "instruction": ""
    }

async def browser_type_text(index: int, text: str):
    """
    向指定元素输入文本内容。

    Args:
        index: 目标输入框元素的索引。
        text: 需要输入的文本内容。
    """
    result = await browser._type_text(index, text)

    yield {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }

async def browser_send_keys(keys: str):
    """
    向当前页面发送键盘快捷键/按键指令。

    Args:
        keys: 发送的按键信息，如"Enter"、"Control+A"等。
    """
    result = await browser._send_keys(keys)

    yield {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }

async def browser_go_back():
    """
    回退浏览器历史记录（相当于点击“后退”按钮）。
    """
    result = await browser._go_back()

    yield {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }

# async def browser_close_browser():
#     """
#     关闭当前浏览器会话，释放相关资源。
#     """
#     result = await browser._close_browser()
#
#     yield {
#         "data": {
#             "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
#         },
#         "instruction": ""
#     }

async def browser_list_tabs():
    """
    获取当前所有已打开标签页的列表。
    """
    result = await browser._list_tabs()

    yield {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }

async def browser_switch_tab(tab_index: int):
    """
    切换到指定索引的标签页。

    Args:
        tab_index: 目标标签页的索引号。
    """
    result = await browser._switch_tab(tab_index)

    yield {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }

async def browser_close_tab(tab_index: int):
    """
    关闭指定索引的标签页。

    Args:
        tab_index: 目标标签页的索引号。
    """
    result = await browser._close_tab(tab_index)

    yield {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }