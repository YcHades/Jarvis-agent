import re
import json
import inspect
from datetime import datetime
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import AsyncGenerator, Union, Dict

from model import LLM
from tool import generate_tool_json, ToolRegistry
from log import (
    AgentLogger,
    LogLevel,
)

AGENT_LOGGER = AgentLogger(level=LogLevel.INFO)


def remove_browser_state(text):
    pattern = re.compile(
        r"============== BROWSER STATE BEGIN ==============(.*?)============== BROWSER STATE END ==============",
        re.DOTALL | re.IGNORECASE
    )
    return pattern.sub(r"[history browser state removed for brevity]", text)


def render_tool_json(tools: dict):
    tool_text = "\n".join([generate_tool_json(tools[tool_name]) for tool_name in tools])
    AGENT_LOGGER.log_task(tool_text, subtitle="LOADING······", title="Loading Tools")
    return tool_text

@dataclass
class ToolCallParseResult:
    exist_tool_call: bool
    tool_json: Union[Dict[str, str], None]
    parse_msg: str

class JarvisAgent:
    """
    jarvis后端agent代理
    """
    def __init__(self,
        init_model_name: str,
        sys_prompt_template: str,
    ):
        self.history = []

        self.llm = LLM(init_model_name)
        self.sys_prompt_template = sys_prompt_template

        # 工具加载
        self.tool_registrar = ToolRegistry()
        self.tool_registrar.load_tools(tools_folder="toolbox")
        self.tools = render_tool_json(self.tool_registrar.tools)

        # system prompt永远在历史记录的最前面
        self.history.append({"role": "system", "content": [{"type": "text", "text": self.sys_prompt_template.format(
            now=datetime.now(),
            knowledge="",
            tools=self.tools
        )}]})

    def save_trajectory(self, output_path="trajectory.json"):
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.history, ensure_ascii=False, indent=4))

    async def chat(self,
        prompt: str,
        llm_name: str = None,
        step_limit: int = None
    ):
        if llm_name is not None:
            self.llm = LLM(llm_name)

        async for chunk in self.reason_and_act(prompt, step_limit):
            print(chunk, end="", flush=True)
        print("\n================================================")
        # print(self.history)

    async def reason_and_act(
        self,
        prompt: str,
        step_limit: int = None
    ) -> AsyncGenerator[str, None]:
        """
        判断LLM输出中是否包含工具执行要求，如果存在则会执行工具
        这一过程会反复进行，直到LLM输出中不再包含工具执行要求
        """
        current_prompt = prompt
        exist_tool_call = True
        steps = 0
        while exist_tool_call and (step_limit is None or steps < step_limit):
            steps += 1
            # 需要修改system_prompt中的当前时间
            self.history[0] = {"role": "system", "content": [{"type": "text", "text": self.sys_prompt_template.format(
                now=datetime.now(),
                knowledge="",
                tools=self.tools
            )}]}

            generator = self.llm.async_stream_generate(current_prompt, history=self.history)
            ai_response = ""
            async for chunk in generator:
                yield chunk
                ai_response += chunk
            self.history.extend([
                {"role": "user", "content": [{"type": "text", "text": remove_browser_state(current_prompt)}]},
                {"role": "assistant", "content": [{"type": "text", "text": ai_response}]}
            ])
            # print(self.history)
            parse_result = self.parse_tool_call(ai_response)
            # AGENT_LOGGER.log_markdown(parsing_message, "Tool call parsing result")

            if parse_result.tool_json:
                AGENT_LOGGER.log_task(str(parse_result.tool_json), subtitle="CALLING······", title="Start tool call")

                tool_call_result = None
                async for status, chunk in self.call_tool(**parse_result.tool_json):
                    if status == "[DONE]":
                        yield "\n* * * * * * * * * * * *\n"
                        tool_call_result = chunk
                    else:
                        yield chunk

                assert tool_call_result is not None, "工具调用没有正确返回最终结果，请检查工具逻辑"

                current_prompt = f"{tool_call_result}\n请你总结并反思工具执行的结果是否符合预期，如果有工具指令，请你遵循执行"
            # 当解析工具调用JSON出错时，需要进行错误处理
            else:
                current_prompt = \
                f"解析工具调用JSON时出现了问题，返回消息如下：\n{parse_result.parse_msg}\n"
                "请你反思：\n"
                "1.是否输出了正确的JSON格式文本；\n"
                "2.是否选择了正确的工具并填入了正确的参数；\n"
                "3.一个特别值得注意的点是，是否没有为字符串参数包裹引号\n"
                "并在反思后尝试重新进行工具调用，对于同一任务最多重新尝试五次"

            exist_tool_call = parse_result.exist_tool_call

        AGENT_LOGGER.log_task(f"总计执行步数：{steps}", subtitle="DONE", title="Task Over")

    async def call_tool(
            self,
            function_name: str,
            arguments: dict
    ) -> AsyncGenerator[tuple, None]:
        """
        根据指定的工具名称调用工具
        """
        # 定义工具返回结果的格式
        class ToolResultFormatValidator(BaseModel):
            data: dict = Field(..., description="工具执行结果")
            instruction: str = Field(..., description="工具附带给模型的指令")

        tool_function = self.tool_registrar.get_tool(function_name)
        # 检查工具是否存在
        if tool_function:
            try:
                # 判断是否是异步生成器
                if inspect.isasyncgenfunction(tool_function):
                    # AGENT_LOGGER.log_markdown("Async tool call", "Tool call type")
                    # 异步流式调用
                    tool_result = {
                        "data": {
                            "final_result": ""
                        },
                        "instruction": ""
                    }
                    async for tool_chunk in tool_function(**arguments):
                        ToolResultFormatValidator.model_validate(tool_chunk)

                        chunk = tool_chunk["data"]["stream_chunk"]
                        yield "[STREAMING]", chunk  # 返回流式数据

                        tool_result["data"]["final_result"] += chunk
                        tool_result["instruction"] = tool_chunk.get("instruction", "") # 将最后一个返回的工具指令作为最终工具指令
                else:
                    # AGENT_LOGGER.log_markdown("Sync tool call", "Tool call type")
                    # 同步调用（适用于普通工具）
                    tool_result = tool_function(**arguments)

                    ToolResultFormatValidator.model_validate(tool_result)
            except Exception as e:
                tool_result = {
                    "data": {
                        "error_message": f"工具执行发生错误，{e}\n工具名：{function_name}"
                    },
                    "instruction": "工具执行错误，请以中文总结并打印错误信息，并且打印具体工具名"
                }
        # 工具未找到的情况
        else:
            tool_result = {
                "data": {
                    "error_message": f"工具执行发生错误，没有找到工具{function_name}"
                },
                "instruction": "工具执行错误，请以中文总结并打印错误信息，并且打印具体工具名"
            }

        # 返回最终结果
        yield "[DONE]", str(
            f"<tool_call_result>\n{tool_result.get('data')}\n</tool_call_result>\n"
            f"<tool_instruction>\n{tool_result.get('instruction')}\n</tool_instruction>"
        )

    def parse_tool_call(
        self,
        ai_response: str
    ) -> ToolCallParseResult:
        """
        解析LLM的输出文本，判断其中是否有工具调用格式，提取工具名称和参数。
        """
        # AGENT_LOGGER.log_task(llm_output_text, subtitle="ROUTING······", title="Parsing LLM output text")

        # 尝试提取文本中的工具调用块
        match = re.search(r'<tool_call>\s*({.*?})\s*</tool_call>', ai_response, re.DOTALL)
        if not match:
            return ToolCallParseResult(False, None, "No tool call found in the llm output text.")
        else:
            # 将工具调用文本转换为dict
            tool_call_text = match.group(1).strip()
            try:
                tool_call_json = json.loads(tool_call_text)
            except json.JSONDecodeError as e:
                return ToolCallParseResult(True, None, f"Error decoding TOOL JSON: {e}")

            # 提取工具名以及填入参数
            function_name = tool_call_json.get('name')
            arguments = tool_call_json.get('arguments')
            if function_name is None:
                return ToolCallParseResult(True, None, "Tool call JSON does not contain key: 'name'")
            if arguments is None:
                return ToolCallParseResult(True, None, "Tool call JSON does not contain key: 'arguments'")

            return ToolCallParseResult(
                True,
                {"function_name": function_name, "arguments": arguments},
                "Successfully extract tool call JSON"
            )
