import os
import yaml
import httpx
import base64
import aiofiles
import traceback
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from typing import AsyncGenerator, Union

load_dotenv()

with open("config.yaml", "r") as f:
    raw_config = os.path.expandvars(f.read())
    config = yaml.safe_load(raw_config)
LLM_CONFIG = config["llm"]

class LLM:
    def __init__(self, model: str="Qwen2.5-VL-7B-Instruct"):
        cfg = LLM_CONFIG.get(model)
        if cfg is None:
            raise ValueError(f"Model '{model}' not found in config.yaml")
        self.async_client = AsyncOpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            http_client=httpx.AsyncClient(verify=False)
        )
        self.model = cfg["model"]

    async def async_generate(
        self,
        prompt: str,
        image_path: Union[str, Path, None] = None,
        history: list[dict] = None
    ) -> str:
        try:
            messages = await self.prepare_messages(prompt, image_path, history)

            chat_response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return chat_response.choices[0].message.content

        except Exception as e:
            return self.handle_error(e)

    async def async_stream_generate(
        self,
        prompt: str,
        image_path: Union[str, Path, None] = None,
        history: list[dict] = None
    ) -> AsyncGenerator[str, None]:
        try:
            messages = await self.prepare_messages(prompt, image_path, history)

            async for chunk in await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            ):
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield content

        except Exception as e:
            yield self.handle_error(e)

    async def prepare_messages(
        self,
        prompt: str,
        image_path: Union[str, Path, None],
        history: list[dict] = None
    ) -> list[dict]:
        messages = history.copy() if history else []

        if image_path:
            base64_image = await self.image_to_base64(image_path)
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
            ]
        else:
            content = [{"type": "text", "text": prompt}]

        messages.append(
            {"role": "user", "content": content}
        )
        return messages

    def handle_error(self, e: Exception) -> str:
        print(f"==========Error: {e}==========")
        print(traceback.format_exc())
        print(f"==========Model: {self.model}==========")
        return f"ERROR: {type(e).__name__} - {str(e)}"

    async def image_to_base64(self, image_path: Union[str, Path]) -> str:
        async with aiofiles.open(image_path, "rb") as image_file:
            content = await image_file.read()
            encoded_string = base64.b64encode(content).decode("utf-8")
        return encoded_string

if __name__ == "__main__":
    print(LLM_CONFIG)

    import asyncio


    async def test():
        llm = LLM("gpt-4o")
        # result = await llm.async_generate("你好，介绍一下你自己")
        # print(result)

        history = [
            {"role": "user", "content": [{"type": "text", "text": "你是三年一班的龙傲天"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "是的，我是三年一班的龙傲天"}]}
        ]

        async for chunk in llm.async_stream_generate("你好，介绍一下你自己", history=history):
            print(chunk, end="")


    asyncio.run(test())