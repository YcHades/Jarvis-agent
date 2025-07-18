import asyncio
import argparse
import json
import os
import subprocess
from typing import List

from agent import JarvisAgent, AGENT_LOGGER
from toolbox.browse import browser
from prompt import jarvis_sys_prompt

async def main():
    parser = argparse.ArgumentParser(description="与 Jarvis 交互")
    parser.add_argument("task", type=str, help="请输入你的指令（英文或中文）")
    args = parser.parse_args()

    jarvis = JarvisAgent(init_model_name="gemini", sys_prompt_template=jarvis_sys_prompt)

    AGENT_LOGGER.log_task(args.task, subtitle="STARTING······", title="Task")

    await jarvis.chat(args.task, "memory/system_memory.txt", step_limit=50)

#     await jarvis.chat(
#     prompt = """\
# 我们需要订购一台新服务器。Emma Lewis 应该已经收集了几家公司的报价并存放在 OwnCloud 上。请按以下步骤操作：
#
# 1. 联系 Emma Lewis（通过 RocketChat）询问报价文件存放位置
# 2. 将报价文件下载到工作区目录（workspace）
# 3. 与 Sarah 讨论服务器需求规格
# 4. 创建 CSV 文件"valid-quotes.csv"，仅包含符合需求的供应商信息：
#    - 必须包含"name"（公司名称）和"price"（报价）两列
# 5. 将文件上传至 OwnCloud 的 Documents/Administrative Specialist 目录
# 6. 为该文件创建公开分享链接（任何人可访问）
# 7. 仅将该链接的 URL 写入 `/workspace/link.txt` 文件
# """
#     , step_limit=20)

    jarvis.save_trajectory("trajectory.json")

    await jarvis.chat( "请分点陈述，总结对于这个任务，你已经做了些什么", step_limit=1)

    cmd = [
        "python_default", "/utils/eval.py",
        "--trajectory_path", "/jarvis/trajectory.json",
        "--result_path", "/jarvis/agent_eval_output.json"
    ]
    env = {"DECRYPTION_KEY": "theagentcompany is all you need", **os.environ}
    proc = subprocess.run(cmd, capture_output=True, env=env, text=True)
    eval_result = proc.stdout + "\n" + proc.stderr

    print("="*10, "BEGIN Eval Result BEGIN", "="*10)
    print(eval_result)
    print("="*10, "END Eval Result END", "="*10)

    await jarvis.chat(f"<eval_result>\n{eval_result}\n</eval_result>" + "\n以上内容为对任务执行情况逐步骤的评估\n\n"
                                    "对比你已经进行完的步骤，请你总结经验，包括：\n"
                                    "1. 对成功的步骤总结经验\n"
                                    "2. 对失败的步骤进行反思\n"
                                    "这些经验可以是针对特定工具的使用经验，或者总结行为原则和方法论", step_limit=1)

    with open("memory/system_memory.txt", mode="r", encoding="utf-8") as f:
        past_memo = f.read()

    new_memo = await jarvis.chat(f"<past_memo>\n{past_memo}\n</past_memo>" + "\n以上是你过去执行任务时积攒的经验\n\n请你将你的最新经验与之进行求同存异的合并，用于给你下次执行相关任务时提供参考。", step_limit=1)

    # print("=" * 10, "BEGIN new memory BEGIN", "=" * 10)
    # print(new_memo)
    # print("=" * 10, "END new memory END", "=" * 10)

    with open("memory/system_memory.txt", mode="w", encoding="utf-8") as f:
        f.write(new_memo)


# def pre_login(browser: BrowserUseLight, sites: List[str]):
#     owncloud_login_actions = [
#         browser._navigate("http://the-agent-company.com:8092"),
#         browser._type_text(
#             "textbox '', clickable, focused, required",
#             "theagentcompany"
#         ),
#         browser._type_text(
#             "textbox '', clickable, required",
#             "theagentcompany"
#         ),
#         browser._click("button '', clickable"),
#     ]
#
#     rocketchat_login_actions = [
#         browser._navigate("http://the-agent-company.com:3000"),
#         browser._type_text(
#             "textbox '', clickable, focused",
#             "theagentcompany"
#         ),
#         browser._type_text(
#             "textbox '', clickable",
#             "theagentcompany"
#         ),
#         browser._click("button 'Login', clickable")
#     ]
#
#     gitlab_login_actions = [
#         browser._navigate("http://the-agent-company.com:8929/users/sign_in"),
#         browser._type_text(
#             "textbox 'Username or primary email'",
#             "root"
#         ),
#         browser._type_text(
#             "textbox 'Password'",
#             "theagentcompany"
#         ),
#         browser._click("button 'Sign in', clickable")
#     ]
#
#     # devnote: plane reset is not stable, and sometimes it fails to launch
#     # in which case the login action will fail, and then we would skip the task
#     plane_login_actions = [
#         browser._navigate("http://the-agent-company.com:8091"),
#         browser._type_text(
#             "textbox 'Email', clickable, focused",
#             "agent@company.com",
#         ),
#         browser._click("button 'Continue'"),
#         browser._type_text(
#             "textbox 'Enter password', clickable",
#             "theagentcompany"
#         ),
#         browser._click("button 'Go to workspace'")
#     ]
#
#     all_login_actions = [
#         ('owncloud', owncloud_login_actions),
#         ('rocketchat', rocketchat_login_actions),
#         ('gitlab', gitlab_login_actions),
#         ('plane', plane_login_actions),
#     ]

if __name__ == "__main__":
    asyncio.run(main())
