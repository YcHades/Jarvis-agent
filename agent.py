import asyncio
import re
import json
import inspect
import traceback
from abc import abstractmethod
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field
from typing import AsyncGenerator, Union, Dict, Any, Tuple, List

from model import LLM
from prompt.reflect_memory import react_block_reflect_check_completion_prompt, react_block_conclude_success_prompt, \
    react_block_analyse_dilemma_prompt
from prompt.system_prompt import jarvis_list_fact_prompt, jarvis_confirm_fact_prompt, \
    jarvis_plan_multi_steps_task_prompt, jarvis_execute_task_step_prompt, jarvis_act_prompt
from tool import generate_tool_schema, ToolRegistry
from log import AgentLogger, LogLevel
from utils import extract_json_codeblock, remove_browser_info_in_the_history

@dataclass
class ToolCallParseResult:
    exist_tool_call: bool
    tool_json: Union[Dict[str, str], None]
    parse_msg: str

class BaseAgent:
    def __init__(
            self,
            init_model_name: str,
            sys_prompt_template: str
    ):
        self.logger = AgentLogger(level=LogLevel.INFO)
        self.llm = LLM(init_model_name)

        self.tool_registrar = ToolRegistry()
        self.tool_registrar.load_tools(tools_folder="toolbox")

        self.history = []
        self.total_steps = 0
        self.sys_prompt_template = sys_prompt_template

    def render_tool_schema_texts(self) -> str:
        tool_schemas = []
        for tool_name, tool_func in self.tool_registrar.tools.items():
            tool_schemas.append(generate_tool_schema(tool_func))

        tools_schema_texts = "\n".join(tool_schemas)
        return tools_schema_texts

    def save_trajectory(self, output_path="outputs/trajectory.json"):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=4)

    def pretty_print_trajectory(self, messages: List[dict], show_full_content: bool=False):
        print()
        def colored(text, color):
            COLORS = {
                "user": "\033[96m",  # 青色
                "assistant": "\033[92m",  # 绿色
                "system": "\033[95m",  # 紫色
                "end": "\033[0m",
            }
            return COLORS.get(color, "") + text + COLORS["end"]

        for idx, msg in enumerate(messages):
            role = msg.get("role", "")
            if role not in ("system", "user", "assistant"):
                continue
            role_disp = colored(f"[{role.upper()}]", role)
            print(f"{idx + 1:02d}. {role_disp}")

            content = msg["content"][0]["text"]
            if isinstance(content, str) and not show_full_content and len(content) > 500:
                preview = content[:250] + "\n ... (已折叠) ... \n" + content[-250:]
                print(f"{preview}")
            else:
                print(content)
        print()

    async def single_turn_chat(
        self,
        prompt: str,
        llm_name: str = None
    ) -> str:
        # 用于发起不进行tool call的单轮对话，但是仍然会使用agent先前的历史记录
        if llm_name is not None:
            self.llm = LLM(llm_name)

        ai_response = ""
        async for chunk in self.llm.async_stream_generate(prompt, history=self.history):
            ai_response += chunk
            print(chunk, end="", flush=True)
        self.history.extend([
            {"role": "user", "content": [{"type": "text", "text": prompt}]},
            {"role": "assistant", "content": [{"type": "text", "text": ai_response}]}
        ])

        return ai_response

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        根据指定的工具名称调用工具
        """
        # 定义工具返回结果的格式
        class ToolResultFormatValidator(BaseModel):
            data: dict = Field(..., description="工具执行结果")
            instruction: str = Field(..., description="工具附带给模型的指令")

        tool_function = self.tool_registrar.get_tool(tool_name)
        if tool_function:
            try:
                # AGENT_LOGGER.log_markdown("Async tool call", "Tool call type")
                tool_result = ""
                async for tool_chunk in tool_function(**arguments):
                    ToolResultFormatValidator.model_validate(tool_chunk)

                    # TODO: 此处暂时保留，后续可以删除工具中还包的一层stream_chunk字段
                    chunk = tool_chunk["data"]["stream_chunk"]
                    yield "[STREAMING]", chunk  # 返回流式数据

                    tool_result += chunk
            except Exception as e:
                tool_result = f"工具执行发生错误，{e}\n工具名：{tool_name}"
        else:
            tool_result = f"工具执行发生错误，没有找到工具{tool_name}"

        # 返回最终结果
        yield "[DONE]", f"<tool_response>\n{tool_result}\n</tool_response>"

    def parse_tool_call(
        self,
        ai_response: str
    ) -> ToolCallParseResult:
        """
        解析LLM的输出文本，判断其中是否有工具调用格式，提取工具名称和参数。
        """
        # AGENT_LOGGER.log_task(llm_output_text, subtitle="ROUTING······", title="Parsing LLM output text")
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
            tool_name = tool_call_json.get('name')
            arguments = tool_call_json.get('arguments')
            if tool_name is None:
                return ToolCallParseResult(True, None, "Tool call JSON does not contain key: 'name'")
            if arguments is None:
                return ToolCallParseResult(True, None, "Tool call JSON does not contain key: 'arguments'")

            return ToolCallParseResult(
                True,
                {"tool_name": tool_name, "arguments": arguments},
                "Successfully extract tool call JSON"
            )

    async def run(self, prompt: str, llm_name: str = None, step_limit: int = None) -> None:
        if llm_name is not None:
            self.llm = LLM(llm_name)

        async for chunk in self._run(prompt, step_limit):
            print(chunk, end="", flush=True)

    @abstractmethod
    async def _run(self, prompt: str, step_limit: int) -> AsyncGenerator[str, None]:
        if False:
            yield ""


class JarvisAgent(BaseAgent):
    """
    jarvis后端agent代理
    """
    def __init__(self, init_model_name: str, sys_prompt_template: str, memory_dir: str):
        super().__init__(init_model_name, sys_prompt_template)

        self.memory_dir = Path(memory_dir)
        self.tool_enhance_dict: Dict[str, Any] = self.load_memory(self.memory_dir / "tool_memory.json")
        self.logger.log_task(str(self.tool_enhance_dict), subtitle="LOADING······", title="Load tool memory")
        self.application_memory: str = self.load_memory(self.memory_dir / "application_memory.txt")
        # self.logger.log_task(self.application_memory, subtitle="LOADING······", title="Load application memory")
        self.methodology_memory: str = self.load_memory(self.memory_dir / "methodology_memory.txt")
        # self.logger.log_task(self.methodology_memory, subtitle="LOADING······", title="Load methodology memory")

        self.temp_memory: str = ""

        self.system_memory = (f"<原则和方法论>{self.methodology_memory}</原则和方法论>\n"
                              f"<特定平台和应用中的注意事项、障碍及其解决方法>{self.application_memory}</特定平台和应用中的注意事项、障碍及其解决方法>\n")
        self.logger.log_task(self.system_memory, subtitle="LOADING······", title="Load system memory")

        self.multi_steps_plan = None

        self.tool_schema_texts = self.render_tool_schema_texts()
        # system prompt永远在历史记录的最前面
        # TODO: 思考为prompt template写类型检查的方法
        self.history.append({"role": "system", "content": [{"type": "text", "text": self.sys_prompt_template.format(
            now=datetime.now(),
            knowledge=self.system_memory,
            tools=self.tool_schema_texts
        )}]})

    def render_tool_schema_texts(self) -> str:
        tool_schemas = []
        for tool_name, tool_func in self.tool_registrar.tools.items():
            # 补充对tool memory的加载
            if tool_name in self.tool_enhance_dict:
                tool_schemas.append(
                    generate_tool_schema(tool_func, self.tool_enhance_dict[tool_name]["tool_description"]))
            else:
                tool_schemas.append(generate_tool_schema(tool_func))

        tools_schema_texts = "\n".join(tool_schemas)
        self.logger.log_task(tools_schema_texts, subtitle="LOADING······", title="Loading Tools")
        return tools_schema_texts

    def load_memory(self, memory_path: str | Path):
        path = Path(memory_path)
        suffix = path.suffix.lower()

        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
                if suffix == ".json":
                    if not text.strip():
                        print("empty json file")
                        return {}
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError as e:
                        print(e)
                        traceback.print_exc()
                        return {}
                else:
                    return text
        except FileNotFoundError as e:
            print(e)
            traceback.print_exc()
            if suffix == ".json":
                return {}
            else:
                return ""

    async def _run(
        self,
        prompt: str,
        step_limit: int = 20
    ) -> AsyncGenerator[str, None]:

        # 所有yield的结果都仅用于给用户展示结果
        # 实际上下文分析始终以agent.history属性中保存的为准
        plan_trajectory = []
        async for chunk in self.multi_step_task_plan(prompt, plan_trajectory):
            yield chunk

        for step_index, (task_step, step_goal) in enumerate(self.multi_steps_plan.items()):
            current_step = f"Step{step_index + 1}: {task_step}\nGoal: {step_goal}"
            self.logger.log_task(current_step, subtitle=f"EXECUTING", title=f"Executing Task Step {step_index + 1}")

            task_step_retry_time_limit = 2
            finish = False
            try_times = 0
            sub_goal_trajectory = []
            while not finish and try_times < task_step_retry_time_limit:
                async for chunk in self.reason_and_act(current_step, step_limit, sub_goal_trajectory):
                    yield chunk

                reflection: Dict[str, str] = {"finish": "no",}
                # 注意：the trajectory used for reflect will remove the ReAct block starter instruction
                async for chunk in self.react_block_reflect(plan_trajectory + sub_goal_trajectory, reflection):
                    yield chunk
                if reflection["finish"].lower() == "yes":
                    finish = True
                else:
                    current_step += "\n该任务步骤的目标还没有达成，请继续执行"
                    yield current_step
                    finish = False
                try_times += 1

            # DEBUG
            # break
            # if step_index == 1:
            #     break

            if not finish:
                self.logger.log_task(f"Done at step {step_index + 1}, agent don't finish this step at {task_step_retry_time_limit} times.", subtitle=f"DONE", title=f"Task Failed")
                return

        self.logger.log_task(f"Agent finish all the task steps， total tool call steps: {self.total_steps}.", subtitle=f"DONE", title=f"Task Finished")
        return

    async def react_block_reflect(self, trajectory: List[dict], reflection: Dict[str, str]):
        # print("\n\n", prompt)
        tasks = [
            self.llm.async_generate(react_block_reflect_check_completion_prompt, history=trajectory),
            self.llm.async_generate(react_block_conclude_success_prompt.format(past_conclusion=self.temp_memory), history=trajectory),
        ]
        finish, conclude = await asyncio.gather(*tasks)
        finish, conclude = extract_json_codeblock(finish), extract_json_codeblock(conclude)
        reflection["finish"] = finish.get("finish", "no")

        lines = [f"- {k}: {v}" for k, v in conclude.items()]
        conclude = "\n".join(lines) + "\n"
        yield conclude

        # 更新系统记忆
        self.temp_memory = "<当前任务执行中积攒的经验>" + conclude + "</当前任务执行中积攒的经验>"
        self.logger.log_task(self.temp_memory, subtitle="LOADING······", title="Load temp memory")
        self.history[0] = {"role": "system", "content": [{"type": "text", "text": self.sys_prompt_template.format(
            now=datetime.now(),
            knowledge=self.system_memory + "\n" + self.temp_memory,
            tools=self.tool_schema_texts
        )}]}

        if reflection["finish"] == "no":
            analysis = ""
            async for chunk in self.llm.async_stream_generate(react_block_analyse_dilemma_prompt, history=trajectory):
                yield chunk
                analysis += chunk
            messages = [
                {"role": "user", "content": [{"type": "text", "text": react_block_analyse_dilemma_prompt}]},
                {"role": "assistant", "content": [{"type": "text", "text": analysis}]}
            ]
            self.history.extend(messages)

        # self.pretty_print_trajectory(trajectory)

    async def multi_step_task_plan(self,
            prompt: str,
            trajectory: List[dict]
    ):
        current_prompt = f"<task>\n{prompt}\n</task>\n\n{jarvis_list_fact_prompt}"

        known_facts = ""
        async for chunk in self.llm.async_stream_generate(current_prompt, history=self.history):
            yield chunk
            known_facts += chunk
        self.history.extend([
            {"role": "user", "content": [{"type": "text", "text": prompt}]},
            {"role": "assistant", "content": [{"type": "text", "text": known_facts}]}
        ])
        yield "\n\n"

        unknown_facts = ""
        async for chunk in self.llm.async_stream_generate(jarvis_confirm_fact_prompt, history=self.history):
            yield chunk
            unknown_facts += chunk
        self.history[-1] = {"role": "assistant", "content": [{"type": "text", "text": f"{known_facts}\n\n{unknown_facts}"}]}
        yield "\n\n"

        multi_steps_plan = ""
        async for chunk in self.llm.async_stream_generate(jarvis_plan_multi_steps_task_prompt, history=self.history):
            yield chunk
            multi_steps_plan += chunk

        self.multi_steps_plan = extract_json_codeblock(multi_steps_plan)
        self.history[-1] = {"role": "assistant",
                            "content": [{"type": "text", "text": f"{known_facts}\n\n{unknown_facts}\n\n* 任务方案可分为如下步骤：\n    {
                                '\n    '.join([f'{i+1}. {x}' for i, x in enumerate(self.multi_steps_plan.keys())])
                            }"}]}
        self.logger.log_task(self.history[-1]["content"][0]["text"], "PLANNING···", "Generate task plan")

        trajectory.extend(self.history[:])

    async def reason_and_act(
            self,
            prompt: str,
            step_limit: int = None,
            trajectory: list = None,
    ) -> AsyncGenerator[str, None]:
        """
        判断LLM输出中是否包含工具执行要求，如果存在则会执行工具
        这一过程会反复进行，直到LLM输出中不再包含工具执行要求
        """
        current_prompt = jarvis_execute_task_step_prompt.format(task_step=prompt)
        exist_tool_call = True
        steps = 0
        # working_memory = []
        while exist_tool_call and (step_limit is None or steps < step_limit):
            # 需要修改system_prompt中的当前时间
            self.history[0] = {"role": "system", "content": [{"type": "text", "text": self.sys_prompt_template.format(
                now=datetime.now(),
                knowledge=self.system_memory,
                tools=self.tool_schema_texts
            )}]}

            user_message = {"role": "user", "content": [{"type": "text", "text": current_prompt}]}
            if steps == 0:
                generator = self.llm.async_stream_generate(current_prompt, history=self.history)
                trajectory.append({"role": "user", "content": [{"type": "text", "text": prompt}]})
            else:
                generator = self.llm.async_stream_generate(jarvis_act_prompt.format(observation=current_prompt), history=self.history)
                trajectory.append(user_message)

            ai_response = ""
            async for chunk in generator:
                yield chunk
                ai_response += chunk

            # 保留最近6轮对话中的浏览器状态，减少上下文
            if len(self.history) > 6:
                history_user_content = self.history[-6]["content"][0]["text"]
                assert self.history[-6].get("role") == "user"
                self.history[-6] = {"role": "user", "content": [{"type": "text", "text": remove_browser_info_in_the_history(history_user_content)}]}
            ai_message = {"role": "assistant", "content": [{"type": "text", "text": ai_response}]}
            self.history.extend([user_message, ai_message])
            trajectory.append(ai_message)

            # print(self.history)
            parse_result = self.parse_tool_call(ai_response)
            # AGENT_LOGGER.log_markdown(parsing_message, "Tool call parsing result")

            if parse_result.tool_json:
                self.logger.log_task(str(parse_result.tool_json), subtitle="CALLING······", title=f"Action Step {steps + 1} ")

                tool_call_result = None
                async for status, chunk in self.call_tool(**parse_result.tool_json):
                    if status == "[DONE]":
                        yield "\n* * * * * * * * * * * *\n"
                        tool_call_result = chunk
                    else:
                        yield chunk

                assert tool_call_result is not None, "工具调用没有正确返回最终结果，请检查工具逻辑"

                current_prompt = f"Observation: \n{tool_call_result}\n"
                # AGENT_LOGGER.log_task(current_prompt, subtitle="PROMPT", title="New prompt")
            # 当没有解析到tool_json时，仅存在没有工具以及工具解析出错两种情况
            else:
                # 如果没有工具，那么以下prompt将不会进入下一次循环，将废弃
                # 反之将进入下一次循环，让Agent反思
                current_prompt = f"Observation: \n{parse_result.parse_msg}\n解析工具调用JSON时出现了问题，请考虑以下情况：1. 是否输出了正确的JSON格式文本；2. 是否选择了正确的工具并填入了正确的参数；3. 一个特别值得注意的点是，是否没有为字符串参数包裹引号"

                # AGENT_LOGGER.log_task(current_prompt, subtitle="PROMPT", title="New prompt")
            exist_tool_call = parse_result.exist_tool_call
            steps += 1

        self.total_steps += steps
        self.logger.log_task(f"当前任务步骤执行步数：{steps}", subtitle="DONE", title="Task Step Over")
        return

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict
    ) -> AsyncGenerator[tuple, None]:
        """
        根据指定的工具名称调用工具
        """

        # 定义工具返回结果的格式
        class ToolResultFormatValidator(BaseModel):
            data: dict = Field(..., description="工具执行结果")
            instruction: str = Field(..., description="工具附带给模型的指令")

        tool_function = self.tool_registrar.get_tool(tool_name)
        if tool_function:
            try:
                # 新增加一个工具指令
                tool_result = {
                    "data": "",
                    "instruction": ""
                }
                async for tool_chunk in tool_function(**arguments):
                    ToolResultFormatValidator.model_validate(tool_chunk)

                    chunk = tool_chunk["data"]["stream_chunk"]
                    yield "[STREAMING]", chunk  # 返回流式数据

                    tool_result["data"] += chunk
                    tool_result["instruction"] = tool_chunk.get("instruction", "")  # 将最后一个返回的工具指令作为最终工具指令
                # 优先使用工具记忆中的工具指令
                if tool_name in self.tool_enhance_dict:
                    tool_result["instruction"] = self.tool_enhance_dict[tool_name]["tool_instruction"]
            except Exception as e:
                tool_result = {
                    "data": f"工具执行发生错误，{e}\n工具名：{tool_name}",
                    "instruction": "工具执行错误，请打印错误信息，并且打印具体工具名"
                }
        else:
            tool_result = {
                "data": f"工具执行发生错误，没有找到工具{tool_name}",
                "instruction": "工具执行错误，请打印错误信息，并且打印具体工具名"
            }

        yield "[DONE]", str(
            f"<tool_response>\n{tool_result.get('data')}\n</tool_response>\n"
            f"<tool_instruction>\n{tool_result.get('instruction')}\n</tool_instruction>"
        )
