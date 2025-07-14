from browser import BrowserEnv, refine_obs, get_agent_obs_text

browser = BrowserEnv()

async def browser_goto_website(
    url: str
):
    """
    使用浏览器访问指定url的网页，返回网页内容

    Args:
        url: 网页url
    """

    obs = refine_obs(
        browser.step(f"goto('{url}')")
    )
    obs["content"] = get_agent_obs_text(obs)

    yield {
        "data": {
            "stream_chunk": str(obs["content"])
        },
        "instruction": ""
    }

async def browser_click_element(
    bid: str
):
    """
    使用浏览器模拟在网页中点击指定bid的元素，返回点击后的网页

    Args:
        bid: 需要点击的元素bid
    """

    obs = refine_obs(
        browser.step(f"click('{bid}')")
    )
    obs["content"] = get_agent_obs_text(obs)

    yield {
        "data": {
            "stream_chunk": str(obs["content"])
        },
        "instruction": ""
    }

async def browser_input(
    bid: str,
    content: str
):
    """
    使用浏览器模拟在网页中聚焦于输入框，并输入给定的内容

    Args:
        bid: 输入框（通常是可聚焦的元素）的bid
        content: 需要输入的内容
    """

    # 对content中的单引号进行转义
    escaped_content = content.replace("'", "\\'")

    obs = refine_obs(
        browser.step(f"fill('{bid}', '{escaped_content}')")
    )
    obs["content"] = get_agent_obs_text(obs)

    yield {
        "data": {
            "stream_chunk": str(obs["content"])
        },
        "instruction": ""
    }

async def browser_noop(wait_ms: float = 1000):
    """
    模拟浏览器执行 noop 操作，可选等待指定毫秒后继续，
    常用于等待页面加载、保持当前状态等场景

    Args:
        wait_ms: 等待时间，单位为毫秒（默认 1000 ms）
    """
    obs = refine_obs(
        browser.step(f"noop({wait_ms})")
    )
    obs["content"] = get_agent_obs_text(obs)

    yield {
        "data": {
            "stream_chunk": str(obs["content"])
        },
        "instruction": ""
    }