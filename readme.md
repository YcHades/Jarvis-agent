# Jarvis
一个超级轻量化的自主Agent框架
## 注意事项
### 启动时需要配置LLM信息
## 前端解析约定
### 视频
```
<video>
{  
  "type": str, [无人机, 监控视频],
  "url": str
}
</video>
```
### 图片
```
<img>
{
  "url": str
}
</img>
```
### 文本
```
<text>
{
  "type": str, [标段进度，标段桥梁路基统计]
  "data": {
    <key>: <value>
  }
}
</text>
```
### 下载
```
<download>
{
  "type": str, [导出计量进度，导出现场进度]
  "auth": str
}
</download>
```
## 开发者文档
### 工具注册
#### 工具注册器
工具注册器ToolRegistry写在tool.py中，负责注册以及管理工具，通常情况下不需要更改  
默认情况下，它会自动加载toolbox文件夹中的所有模块以及其中的工具
#### 工具文件夹结构
工具通常放置在toolbox文件夹下，文件夹结构如下：
```
toolbox/
├── __init__.py       # 工具包初始化文件（可以为空）
├── camera.py         # 摄像头相关工具（示例）
├── drone.py          # 无人机相关工具（示例）
├── section.py        # 标段相关工具（示例）
```
具有相关功能的工具放置在一个python文件中，这被视作一个模块，实际使用时模块可以被选择性加载
```
# 仅加载camera模块中的工具，在tool.py中书写
registrar.load_tools(tools_folder="toolbox", modules=["camera"])
```
#### 模块文件结构
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
    
# 随后可以定义工具
def tool_function
······
```
工具是一个函数，内容其实也很自由，但有两点是必需的：  
一个是需要谷歌风格的docstring，其中需要写明工具功能以及所需参数，并且书写格式要求严格；  
另一个是需要返回一个dict，dict中的内容也是固定的：  
1. data字段，其值也是一个dict，包含工具返回的数据（比如执行结果）
2. instruction字段，其值是一个str，包含工具给LLM的指令  
看起来像这样：
```
{
    "data": {},
    "instruction": ""
}
```
如果工具需要**返回中间结果**给前端展示，或者需要**流式输出**，则需要在data中给定字段**stream_chunk**  
（同时，工具函数必须是一个异步函数）  
看起来像这样：
```
# 这个示例用于使用前端解析约定展示一个视频
{
    "data": {
        "stream_chunk": AIMessageChunk(content=f"<video>\n{url}\n</video>\n"
            "直播画面载入中······")
    },
    "instruction": ""
}
```
（目前中间结果、异步以及流式都必须以AIMessageChunk为载体，如果你熟悉langchain的话就知道我在说什么，不过这一局面不会持续太久（应该））  
整个工具的示例如下：  
```
# 一个工具的注释必须按照给定的格式书写，一个符号都不能差
def get_drone_live_url(device_type: str):
    """
    获取无人机直播链接
    
    Args:
        device_type (str): 设备类型
    """
    
    # 这中间可以写任何的代码逻辑
    
    return {
        "data": {
            # 可以写任何返回值（流式的话就限定死是stream_chunk了）
            "meta_info": "HELLO LLM!",
        },
        "instruction": "Greet to LLM"
    }
```
### 提示书写
目前提示部分还没有完全抽象出来，目前一个项目只有一个系统提示  
#### 提示与工具调用
为了使得模型工具调用运行正常，提示中写有一大段与工具调用有关的内容：
```
f"""### TOOLS ###
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
如果你要对这段提示进行修改，请你清楚修改的目的以及可能的变化，并相应地修改**agent.py**中与工具调用相关的代码  
#### 工具提示
参考工具返回的instruction，这部分实际上也是一段提示，在每次工具调用之后提供给模型，可以参考现有工具的写法  
比如，当需要前端展示特定的内容（比如多媒体内容：图片、视频等）时，就可以通过书写工具提示来使得模型输出符合“前端解析约定”格式的内容  
示例如下：
```
# 以下工具提示会让模型打印出符合“前端解析约定”中的“视频”格式
{
    "data": {},
    "instruction": "请严格按照给定格式打印<raw-content>标签中的内容"
                   "（包括其中的其他xml标签（不包括<raw-content>标签本身）），这将会播放无人机直播链接："
                   "\n\n<raw-content>\n"
                   f"<video>\n{json_content}\n</video>\n"
                   "直播画面载入中······"
                   "\n</raw-content>\n\n"
                   "除此以外，你不需要任何其他的操作"
}
```
输出会是这样：
```
<video>
{"type": "监控视频", "data": {"url": "rtsp://xxxxxx"}}
</video>

监控画面载入中····
```
至于前端想解析成什么样，那就看前端小伙伴的心情了，前端解析约定也可以自己和前端约定好格式