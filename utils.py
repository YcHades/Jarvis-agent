import re
import json
import traceback
from typing import Dict, Any


def remove_browser_info_in_the_history(text: str) -> str:
    pattern = re.compile(
        r"============== BROWSER INFO BEGIN ==============(.*?)============== BROWSER INFO END ==============",
        re.DOTALL | re.IGNORECASE
    )
    return pattern.sub(r"[history browser info removed for brevity]", text)

def extract_json_codeblock(md_text: str) -> Dict[str, Any]:
    match = re.search(
        r"```json\s*\n(.*?)\n```",
        md_text,
        re.DOTALL | re.IGNORECASE
    )
    if not match:
        print("Error: can't found json block, return empty dict")
        return {}
    block = match.group(1)
    try:
        return json.loads(block.strip())
    except Exception as e:
        print(e)
        traceback.print_exc()
        return {}