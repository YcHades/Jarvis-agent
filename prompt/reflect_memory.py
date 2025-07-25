


react_block_reflect_check_completion_prompt = """\
请你对当前任务步骤的执行情况进行总结，判断该步骤是否已经完成

请将你的最终判断格式化为一个JSON，格式如下：
```json
{{
    "finish": "<yes/no>"
}}
```
"""

react_block_conclude_success_prompt = """\
请回顾在当前的任务步骤中你成功完成了哪些“一小步”，并总结你是如何完成这些一小步的。
尤其是对于那些你反复执行、大费周折才最终完成的“一小步”，请你着重总结，提炼出其中让你最终完成这一小步的正确行为，组合出一条成功的路径。

要求：你的总结需要能够被用于指导其他人绕过你碰到的障碍，在与你相同的环境下又快又好地完成同样的任务。

{past_conclusion}
以上为以前的总结，请你求同存异的合并，给出新的结果

请将你的总结格式化为一个JSON，格式如下：
```json
{{
    "<name_of_success_small_step_1>": "<the way you made it>",
    "<name_of_success_small_step_2>": "<the way you made it>",
    ··· 
    "<name_of_success_small_step_n>": "<the way you made it>",
}}
```
"""

react_block_analyse_dilemma_prompt = """\
当前任务步骤似乎还是没能够完成，请你分析当前的任务障碍是什么，并给出一个接下来的行为方案。
要求：
- 优先从自己身上找原因：优先反思先前的行为轨迹中是不是有什么遗漏和失误，是不是对于工具特点理解不充分导致在使用上有些失误
- 避免陷入惯性：避免原地踏步，尝试一些不一样的行为
- 自主探索与尝试：不要寻求用户帮助解决问题，你可以自主探索可能的解决方案，或者进行一些技术尝试

请按照如下模板输出：
* 当前任务步骤仍然有以下问题：
    1. xxx
    2. xxx
    ······
    
* 考虑尝试如下行为：
    1. xxx
    2. xxx
    ······

* 接下来将重新加载任务步骤和目标······
"""