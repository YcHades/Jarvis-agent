
import os
import asyncio
import argparse
import subprocess

from baseline import ReActAgent
from prompt.baseline_prompt import react_sys_prompt

BASELINE = "ReAct"

async def main():
    parser = argparse.ArgumentParser(description="与Agent交互")
    parser.add_argument("task", type=str, help="请输入你的指令（英文或中文）")
    parser.add_argument("task_name", type=str, help="任务名")
    args = parser.parse_args()

    react_agent = ReActAgent(init_model_name="gemini", sys_prompt_template=react_sys_prompt)

    react_agent.logger.log_task(args.task, subtitle="STARTING······", title="Task")
    await react_agent.run(args.task, step_limit=50)
    react_agent.save_trajectory(f"outputs/{BASELINE}/{args.task_name}/trajectory.json")

    cmd = [
        "python_default", "/utils/eval.py",
        "--trajectory_path", f"/jarvis/outputs/{BASELINE}/{args.task_name}/trajectory.json",
        "--result_path", f"/jarvis/outputs/{BASELINE}/{args.task_name}/eval_result.json"
    ]
    env = {"DECRYPTION_KEY": "theagentcompany is all you need", **os.environ}
    proc = subprocess.run(cmd, capture_output=True, env=env, text=True)
    # eval_result = proc.stdout + "\n" + proc.stderr

if __name__ == "__main__":
    asyncio.run(main())