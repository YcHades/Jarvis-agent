
from agent import BaseAgent
from utils import remove_browser_info_in_the_history

class ReActAgent(BaseAgent):
    def __init__(self, init_model_name: str, sys_prompt_template: str):
        super().__init__(init_model_name, sys_prompt_template)

        self.tool_schema_texts = self.render_tool_schema_texts()
        self.history.append(
            {"role": "system", "content": [{"type": "text", "text": self.sys_prompt_template.format(
                tools=self.tool_schema_texts
            )}]}
        )
        self.logger.log_task(self.history[0]["content"][0]["text"], "LOADING···", "Loading ReAct system memory")

    async def _run(
            self,
            prompt: str,
            step_limit: int = None
    ):
        current_prompt = "Question: \n" + prompt
        self.logger.log_task(current_prompt, "READING···", "Reading Task")
        exist_tool_call = True
        steps = 0
        while exist_tool_call and (step_limit is None or steps < step_limit):

            steps += 1
            ai_response = ""
            async for chunk in self.llm.async_stream_generate(current_prompt, history=self.history):
                yield chunk
                ai_response += chunk
            # 保留最近6轮对话中的浏览器状态，减少上下文
            if len(self.history) > 6:
                history_user_content = self.history[-6]["content"][0]["text"]
                self.history[-6] = {"role": "user", "content": [
                    {"type": "text", "text": remove_browser_info_in_the_history(history_user_content)}]}
            self.history.extend([
                {"role": "user", "content": [{"type": "text", "text": current_prompt}]},
                {"role": "assistant", "content": [{"type": "text", "text": ai_response}]}
            ])
            # print(self.history)
            parse_result = self.parse_tool_call(ai_response)
            # AGENT_LOGGER.log_markdown(parsing_message, "Tool call parsing result")

            if parse_result.tool_json:
                self.logger.log_task(str(parse_result.tool_json), subtitle="CALLING······", title="Start tool call")

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

        self.logger.log_task(f"总计执行步数：{steps}", subtitle="DONE", title="Task Over")
        return