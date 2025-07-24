import asyncio
import json
from browser import BrowserUseLight


browser = BrowserUseLight()

async def browser_navigate( url: str, new_tab: bool = False):
    """
    使用浏览器导航至指定 URL，支持新标签页打开。

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
    在浏览器当前页面中，根据元素索引点击页面元素
    如果元素具有链接，支持新标签页打开链接。

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
    获取当前浏览器状态，包括：
    1. 当前浏览器显示的标签页的url
    2. 当前浏览器显示的标签页的title
    3. 当前浏览器打开的所有标签页信息（包括各标签页的url和title）
    4. 当前浏览器显示的标签页的可交互元素信息（包括元素index、tag、text等，这些信息都来自标签页的DOM树）

    注意：
    - 该工具使用后将会给浏览器当前标签页上的可交互元素绘制标记框以及元素索引，重复使用将会更新绘制，在页面变化后需要及时利用这个工具更新
    - 该工具对于文本、视觉内容信息的提取可能比较简略，富内容信息需要使用browser_extract_content_by_vision工具补充提取
    - 该浏览器状态获得后最多会在上下文中维持六轮对话，然后需要重新获取
    """
    result = await browser._get_browser_state()

    yield {
        "data": {
            "stream_chunk": json.dumps(result)
        },
        "instruction": ""
    }

async def browser_extract_content(query: str = "请详细地描述这个网页", need_mark: bool = False):
    """
    根据指令，使用视觉模型从浏览器页面截图以及HTML源码中提取当前浏览器的标签页中的相关内容

    注意：
    - browser_get_browser_state将为浏览器当前标签页上的可交互元素绘制的标记框以及元素索引，这些标记也可以被视觉模型识别到，重新进入该页面将移除这些标记
    - 视觉识别模型不是绝对正确的，包括对页面内容的提取以及元素索引的数字也存在出错可能
    - 作为建议，在对当前网页内容没有把握时，可以先使用全面描述的query，再使用更细致的query，以免陷入某种偏见

    Args：
        query: 给视觉模型的内容提取的指令，默认为：请详细地描述这个网页
        need_mark: 自动使用browser_get_browser_state为页面的可交互元素绘制标记，默认为False（但是当前页面如果在先前的action中调用过browser_get_browser_state，那么即使该参数设置为False仍然会有标记）
    """
    if need_mark:
        await browser._get_browser_state()
    tasks = [browser._extract_content_by_vision(query), browser._extract_content(query, True)]
    vision_result, html_result = await asyncio.gather(*tasks)

    yield {
        "data": {
            "stream_chunk": str({
                "vision_result": vision_result,
                "html_result": html_result
            })
        },
        "instruction": ""
    }

async def browser_type_text(index: int, text: str):
    """
    向当前浏览器显示的标签中的指定元素输入文本内容。

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
    向当前浏览器显示的标签页发送键盘快捷键/按键指令。

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
    触发浏览器当前标签页的"回退"
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
    获取浏览器当前所有已打开标签页的列表。
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
    切换到浏览器中指定索引的标签页。

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
    关闭浏览器中指定索引的标签页。

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

async def browser_wait(seconds: int = 5):
    """
    停顿等待一定时长，常用于等待浏览器页面元素的更新、加载或动态内容渲染。

    Args:
        seconds: 等待的秒数，默认5秒。
    """
    await asyncio.sleep(seconds)
    result = f"已等待 {seconds} 秒"

    yield {
        "data": {
            "stream_chunk": result
        },
        "instruction": ""
    }