import json
import subprocess

async def run_cmd(
    command: str,
):
    """
    执行一个完整的 shell 命令字符串，并返回执行结果。

    Args:
        command: 要执行的命令，如 "ls -la /home"
    """
    result = subprocess.run(
        command,
        shell=True,  # 允许字符串形式命令
        capture_output=True,  # 捕获标准输出和错误
        text=True,  # 输出为字符串（不是字节）
        cwd = "/workspace"
    )

    result =  {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip()
    }

    yield {
        "data": {
            "stream_chunk": json.dumps(result, ensure_ascii=False, indent=2)
        },
        "instruction": ""
    }