import importlib
import inspect
import json
import os
import re
from typing import Callable, List, Union, get_origin, get_args, Dict, Any


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register_tool(self, tool_name: str, tool_func: Callable):
        """注册工具函数到工具注册器"""
        self.tools[tool_name] = tool_func

    def get_tool(self, tool_name: str):
        """通过工具名获取工具函数"""
        return self.tools.get(tool_name)

    def load_module_tools(self, module_name: str):
        """根据功能模块名称加载工具"""
        try:
            module = importlib.import_module(f"toolbox.{module_name}")

            # 遍历模块中的所有属性，确保它们是“可调用的”、不是私有的，并且定义在当前模块中
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                        callable(attr)
                        and not attr_name.startswith('_')
                        and getattr(attr, '__module__', None) == module.__name__  # 检查函数是否定义在当前模块中
                ):
                    self.register_tool(attr_name, attr)
        except Exception as e:
            print(f"Error loading module 'toolbox.{module_name}': {e}")

    def load_tools(self, tools_folder: str="toolbox", modules: List[str] = None):
        """根据模块列表加载工具"""
        # 如果没有指定模块列表，加载所有模块
        if modules is None:
            modules = [
                filename[:-3] for filename in os.listdir(tools_folder)
                if filename.endswith('.py') and filename != '__init__.py'
            ]

        # 加载每个指定模块中的工具
        for module_name in modules:
            self.load_module_tools(module_name)


def generate_tool_schema(func: Callable, enhance_des: str | None = None) -> str:
    """将工具函数转化为json描述"""

    # 用于将python函数类型映射为json schema类型
    TYPE_MAPPING = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        list: "array",
        tuple: "array",
        dict: "object",
        type(None): "null"
    }

    func_name = func.__name__
    doc = inspect.getdoc(func)
    signature = inspect.signature(func)

    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    # 解析docstring中的参数描述
    param_descriptions = {}
    if doc:
        # 使用正则表达式提取 "Args:" 部分及其下的内容，直到下一个段落（如 Returns: 或文档结束）
        match = re.search(r"Args:\s*(.*?)(?=\s*(?:Returns:|$))", doc, re.DOTALL)
        if match:
            args_section = match.group(1)
            param_lines = args_section.strip().splitlines()
            for line in param_lines:
                # group_0: 参数名, group_1: 参数描述
                param_match = re.match(r"\s*(\w+)\s*:\s*(.*?)\s*$", line.strip())
                if param_match:
                    param_name, param_desc = param_match.groups()
                    param_descriptions[param_name] = param_desc.strip()

    # 根据签名信息和提取的描述生成参数信息
    for param_name, param in signature.parameters.items():
        param_type = param.annotation
        if param_type == inspect._empty:
            param_type = str

        # 如果是 Union 类型，则处理为 oneOf
        if get_origin(param_type) is Union:
            possible_types = get_args(param_type)
            param_info = {"oneOf": []}
            for possible_type in possible_types:
                if get_origin(possible_type) is list:
                    param_info["oneOf"].append({
                        "type": "array",
                        "items": {
                            "type": TYPE_MAPPING.get(get_args(possible_type)[0], "string")
                        }
                    })
                else:
                    param_info["oneOf"].append({"type": TYPE_MAPPING.get(possible_type, "string")})
        # 处理 List 类型
        elif get_origin(param_type) is list:
            param_info = {
                "type": "array",
                "items": {
                    "type": TYPE_MAPPING.get(get_args(param_type)[0], "string")
                }
            }
        else:
            param_info = {"type": TYPE_MAPPING.get(param_type, "string")}

        # 获取参数描述
        if param_name in param_descriptions:
            param_info["description"] = param_descriptions[param_name]
        else:
            param_info["description"] = f"{param_name}暂时没有参数描述"

        # 判断参数是否有默认值
        if param.default != inspect._empty:
            param_info["default"] = param.default

        parameters["properties"][param_name] = param_info

        # 对于没有默认值的参数，写入required中
        if param.default == inspect._empty:
            parameters["required"].append(param_name)

    if enhance_des is not None:
        func_des = enhance_des
    elif doc:
        func_des = doc.split("\nArgs:")[0]
    else:
        func_des = "暂无函数描述"

    tool_schema = {
        "type": "function",
        "function": {
            "name": func_name,
            "description": func_des,
            "parameters": parameters
        }
    }

    return json.dumps(tool_schema, ensure_ascii=False)


# if __name__ == '__main__':
#     print(TOOL_REGISTRAR.tools.keys())
#     print(generate_tool_json(TOOL_REGISTRAR.tools["get_and_play_cameras_playbacks_url_by_fuzzy_name"]))
