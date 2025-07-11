import base64
from pathlib import Path
from openai import OpenAI

api_key = "sk-mpgDJJe9yhJ3dynDUSM8HsVMiWcSScXArvp635WPwi5aJ6CL"
base_url = "http://35.220.164.252:3888/v1"

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

async def gpt4o_describe_image(
    image_path: str
):
    """
    使用 GPT-4o 对图像进行识别与理解。

    Args:
        image_path (str): 本地图像路径
        prompt (str): 对图像的任务描述，比如 OCR、场景描述、信息提取
        model (str): 使用的 OpenAI 模型，默认 gpt-4o
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