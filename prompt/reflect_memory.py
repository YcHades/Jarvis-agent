


react_block_reflect_prompt = """\
请你对当前任务步骤的执行情况进行总结，判断该步骤是否已经完成。
- 如果已经完成，请你进行复盘，总结成功的经验，提高相似任务的执行成功率和效率；
- 如果没能完成，请你分析失败的原因，考虑所有可能的情况特别是反思前的执行动作是不是存在一些问题。

请将输出内容格式化为一个JSON，格式如下：
```json
{{
    "finish": "<yes/no>",
    "analysis": "<your analysis and experience>"
}}
```
"""