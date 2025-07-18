
import os
import base64
from pathlib import Path
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)

async def gpt4o_describe_image(
    image_path: str
):
    """
    使用 GPT-4o 对图像进行识别与理解。

    Args:
        image_path: 本地图像路径
    """
    image_bytes = Path(image_path).read_bytes()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": "请描述这张图片的内容，并尽可能提取出图中文字。"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]}
        ],
        temperature=0.2,
        max_tokens=1024
    )

    result = response.choices[0].message.content

    yield {
        "data": {
            "stream_chunk": result
        },
        "instruction": ""
    }