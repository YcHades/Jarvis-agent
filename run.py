import asyncio
import argparse

from agent import JarvisAgent
from prompt import jarvis_sys_prompt


async def main():
    parser = argparse.ArgumentParser(description="与 Jarvis 交互")
    parser.add_argument("prompt", type=str, help="请输入你的指令（英文或中文）")
    args = parser.parse_args()

    jarvis = JarvisAgent(init_model_name="claude", sys_prompt_template=jarvis_sys_prompt)

    await jarvis.chat(args.prompt)

if __name__ == "__main__":
    asyncio.run(main())
