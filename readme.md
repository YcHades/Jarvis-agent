# Jarvis
一个超级轻量化的自主Agent框架，具有进行浏览器操作和运行CMD指令的能力
## 快速开始
**我们建议在docker容器环境下运行agent，因其具有操作CMD的能力，可能对您的计算机造成影响！！！**  
**项目根目录提供了用于构建docker镜像的dockerfile**
### 环境
在项目根目录终端运行：
```shell
conda create -n jarvis python=3.12
conda activate jarvis
pip install -r requirements.txt
```
### 配置LLM
1. 参考config.yaml，填写要使用的LLM的配置信息
2. 在项目根目录创建.env文件，并填写config中所需的环境变量，一个示例如下：  
    ```dotenv
    BASE_URL=https://***/v1
    API_KEY=***
    ```
### 运行
在run.py中指定agent使用的模型，然后运行run.py，一个运行示例如下：
   ```shell
   python run.py "你好"
   ```
## 文档
### 工具注册
如果需要添加新的工具，可以参考以下内容：
#### 工具注册器
工具注册器类ToolRegistry写在tool.py中，负责注册以及管理工具，通常情况下不需要更改  
默认agent类实例化了一个工具注册器，可见agent.py，它会自动加载toolbox文件夹中的所有模块以及其中的工具
#### 工具文件夹结构
工具默认放置在toolbox文件夹下，文件夹结构如下：
```
toolbox/
├── camera.py         # 摄像头相关工具（示例）
├── drone.py          # 无人机相关工具（示例）
├── section.py        # 标段相关工具（示例）
```
具有相关功能的工具放置在一个python文件中，这被视作一个模块，实际使用时模块可以被选择性加载
```
# 仅加载camera模块中的工具
tool_registrar.load_tools(tools_folder="toolbox", modules=["camera"])
```
#### 工具模块结构
实际上模块python文件的组织比较自由，一个推荐的结构如下：
```
# 在最开始定义共有的一些参数变量以及工具所需的私有函数
common_headers = {
    'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
}

def _drone_login(): # 单下划线“_”开头的私有函数，不会被工具注册器读取到
    """
    登录无人机控制系统
    """
    pass
```
随后可以定义工具，示例结构如下：
```
async def tool_A(
    arg_1: str
):
    """
    对工具的描述

    Args:
        arg_1: 参数作用
    """
    ······逻辑代码······
    yield {
        "data": {
            "stream_chunk": <工具执行结果>
        },
        "instruction": ""
    }
```
作为agent工具的函数，其参数类型、函数描述(docstring)、返回值的结构都必须严格对应  
工具支持流式输出，结果会通过stream_chunk在运行中途打印出来  
工具支持一个工具提示(instruction)，用于告知LLM拿到工具结果之后可以/应该做些什么，用于人为的fix工作流，但也可以为空，完全由LLM自己决定做什么
### 提示/prompt
提示见于prompt.py
#### 提示与工具调用
为了使得模型工具调用运行正常，提示中写有一大段与工具调用有关的内容：
```
### TOOLS ###
对于用户的一些请求，你可能需要调用工具来完成。

在<tools> </tools> XML标签中提供了你能够选择调用的工具的签名：

<tools>
{tool_json_render_description(registrar.tools)}
</tools>

对于每个工具调用，返回一个带有工具名称和参数的JSON对象，并写在<tool_call> </tool_call> xml标签中：
<tool_call>
{{{{"name": <function-name>, "arguments": <args-json-object>}}}}
</tool_call>

每个工具调用执行完毕之后，工具将会输出一个结果，写在<tool_response> </tool_response> xml标签中，\
同时还可能附带一个工具指令，写在<tool_instruction> </tool_instruction> xml标签中。
用户会在每个工具执行完毕之后，将上述工具的输出提供给你，对此你需要完成以下任务：
1. 如果存在工具指令，请你首先完成工具指令；
2. 如果没有工具指令，则你需要对工具执行结果进行总结；
3. 除此之外你不需要进行任何其他的额外的操作或者行为。
```
这部分**不建议修改**，因为agent的工具调用需要固定格式的LLM输出才能完成，这段提示正是为了这一目的  
除此以外，提示的其他内容都可以修改，可以参考**prompt.py**中已有的系统提示