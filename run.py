import asyncio
import argparse
import json
import os
import re
import subprocess
import traceback
from typing import List, Any, Optional, Dict, Tuple

from agent import JarvisAgent, extract_json_codeblock
from prompt.system_prompt import jarvis_sys_prompt

def get_TAC_evaluation(task_name: str) -> Tuple[str, str]:
    cmd = [
        "python_default", "/utils/eval.py",
        "--trajectory_path", f"/jarvis/outputs/ours/{task_name}/trajectory.json",
        "--result_path", f"/jarvis/outputs/ours/{task_name}/agent_eval_output.json"
    ]
    env = {"DECRYPTION_KEY": "theagentcompany is all you need", **os.environ}
    proc = subprocess.run(cmd, capture_output=True, env=env, text=True)
    eval_result = proc.stdout + "\n" + proc.stderr

    print("=" * 10, "BEGIN Eval Result BEGIN", "=" * 10)
    print(eval_result)
    print("=" * 10, "END Eval Result END", "=" * 10)

    with open("/instruction/checkpoints.md", "r") as f:
        checkpoints = f.read()

    print("=" * 10, "BEGIN Checkpoints BEGIN", "=" * 10)
    print(checkpoints)
    print("=" * 10, "END Checkpoints END", "=" * 10)

    return eval_result, checkpoints

async def main():
    parser = argparse.ArgumentParser(description="与Agent交互")
    parser.add_argument("task_name", type=str, help="任务名")
    parser.add_argument("task", type=str, help="请输入你的指令（英文或中文）")
    args = parser.parse_args()

    jarvis = JarvisAgent(
        init_model_name="gemini",
        sys_prompt_template=jarvis_sys_prompt,
        memory_dir="memory"
    )

    jarvis.logger.log_task(args.task, subtitle="STARTING······", title="Task")

    await jarvis.run(args.task, step_limit=50)

    jarvis.save_trajectory(f"outputs/ours/{args.task_name}/trajectory.json")

    # Only could run in the TAC docker env
    eval_result, checkpoints = get_TAC_evaluation(args.task_name)

    print("\n\n")

    await jarvis.single_turn_chat("请分点陈述，总结对于这个任务，你已经做了些什么")

    conclude_prompt = f"""\
<checkpoints>\n{checkpoints}\n</checkpoints>
<eval_result>\n{eval_result}\n</eval_result>
以上内容为该任务的得分点和最终的得分评估

对比你已经进行完的步骤，请你总结经验，包括：
1. 对成功的步骤总结经验
2. 对失败的步骤进行反思
"""
    await jarvis.single_turn_chat(conclude_prompt)

    print("\n\n")

    tool_enhance_prompt = f"""\
请你根据本次任务的实际使用情况，对所用工具进行总结和反馈，并对每个工具的功能描述和工具指令进行优化或补充。
请参考最开始给你的那些工具描述，在其基础上对需要的工具进行优化修改。
browser_get_browser_state，browser_extract_content两个工具为核心工具，对其描述需要谨慎修改。
你的目标是让这些描述和指令更加准确，并且有助于你下次更高效、更精准地调用工具。
<tips>
工具描述：对工具整体功能、作用、注意事项或任意你觉得需要的描述
工具指令：工具执行完之后附带的一个指令，用于控制工具执行完之后的行为
</tips>

对于你的修改，请你最终以如下格式输出：
```json
{{
    "<tool_name>": {{
        "tool_description": "<the tool description you wanna change to ",
        "tool_instruction": "<the tool instruction you wanna change to >"
    }}
    ··· # 你可以修改任意个工具
}}
```
"""
    tool_enhance_dict = jarvis.tool_enhance_dict.copy()
    tool_enhance_result = await jarvis.single_turn_chat(tool_enhance_prompt)
    tool_enhance_dict.update(
        extract_json_codeblock(tool_enhance_result)
    )
    with open("memory/tool_memory.json", "w") as f:
        f.write(json.dumps(tool_enhance_dict, ensure_ascii=False, indent=2))

    print("\n\n")

    application_enhance_prompt = f"""\
请你对本次任务中碰到的特定平台和应用中的障碍及其解决方法进行反思和总结，形成'特定平台和应用中的注意事项、障碍及其解决方法'。
你的目标是在下次进行相关任务并碰到类似障碍时，能够很快应用正确的解决方案。
<tips>
你的总结应该足够细致和详细，为下次面临同样的情形时提供足够的参考
不要进行空泛的总结，要具体到问题和方法
</tips>

对于你的总结，请你最终以如下格式输出：
```json
{{
    "<application_name>": {{
        "<problem>": "<solution>"
    }}
    ···
}}
```
"""
    await jarvis.single_turn_chat(application_enhance_prompt)

    application_memo = await jarvis.single_turn_chat("请你将你最新的'特定平台和应用中的注意事项、障碍及其解决方法'与你先前的行求同存异的合并，用于给你下次执行相关任务时提供参考")

    with open("memory/application_memory.txt", mode="w", encoding="utf-8") as f:
        f.write(application_memo)

    print("\n\n")

    methodology_enhance_prompt = f"""\
请你对本次任务中碰到的其他困境进行总结，关注你做对了什么和做错了什么，形成后续任务的'原则和方法论'。
你的目标是在下次以更正确的行为方式解决任务。
<tips>
你的总结应该足够细致和详细，为下次面临同样的情形时提供足够的参考
不要进行空泛的总结，要具体到问题和方法
</tips>

对于你的总结，请你最终以如下格式输出：
```json
{{
    "<dilemma>": "<methodology>"
    ···
}}
```
"""
    await jarvis.single_turn_chat(methodology_enhance_prompt)

    methodology_memo = await jarvis.single_turn_chat("请你将你最新的'原则和方法论'与你先前的进行求同存异的合并，用于给你下次执行相关任务时提供参考")

    with open("memory/methodology_memory.txt", mode="w", encoding="utf-8") as f:
        f.write(methodology_memo)


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
