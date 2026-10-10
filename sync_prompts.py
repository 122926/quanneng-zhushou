# -*- coding: utf-8 -*-
"""同步脚本：从根目录 prompts.json 生成 edgeone/functions/api/prompts.js（EdgeOne 端提示词单一来源）。

改人格流程：
    1. 编辑根目录 prompts.json 里的 work / emotion 两段文字；
    2. 运行本脚本：python sync_prompts.py
    3. 把 edgeone 目录推送到 GitHub，EdgeOne 自动重新部署。
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROMPTS_FILE = BASE / "prompts.json"
OUT = BASE / "edgeone" / "functions" / "api" / "prompts.js"


def main() -> int:
    try:
        data = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print("错误：缺少或损坏 prompts.json（提示词单一来源）：%s" % exc)
        return 1
    if not isinstance(data, dict) or not data.get("work") or not data.get("emotion"):
        print("错误：prompts.json 必须包含 work 和 emotion 两段提示词")
        return 1

    lines = [
        "// 由 sync_prompts.py 从根目录 prompts.json 自动生成，请勿手改。",
        "// 改人格请编辑根目录 prompts.json，然后运行：python sync_prompts.py",
        "export const PROMPTS = " + json.dumps(data, ensure_ascii=False, indent=2) + ";",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("written:", OUT)
    print("bytes:", OUT.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
