# -*- coding: utf-8 -*-
"""生成腾讯云 SCF 单文件部署版 scf_handler.py（HTML 与提示词均内嵌为 repr 字符串）。
提示词来自根目录 prompts.json（单一来源），改人格只改 prompts.json。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
HTML = (BASE.parent / "全能助手.html").read_text(encoding="utf-8")
assert "'''" not in HTML, "HTML contains ''' which breaks embedding"

SRC = BASE / "scf_handler.py"
if SRC.exists():
    SRC.unlink()

handler_code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全能助手 · 手机网页版 —— 腾讯云 SCF 云函数版（单文件部署）

部署步骤见同目录《部署说明.md》。
环境变量（在 SCF 控制台配置，支持最多 3 组 API，自动切换）：
  组 1（兼容旧变量）：API_KEY_1 或 API_KEY（必填），API_BASE_URL_1/API_BASE_URL、API_MODEL_1/API_MODEL、API_NAME_1 可选
  组 2/3（可选）：API_KEY_2 / API_KEY_3，配 API_BASE_URL_2/3、API_MODEL_2/3、API_NAME_2/3
  MAX_HISTORY    可选，默认 20
  TEMPERATURE    可选，默认 0.7
请求体可带 provider: "1"|"2"|"3" 指定模型；不带则按顺序自动尝试，失败自动换下一组。
"""

import json
import os
import urllib.error
import urllib.request

HTML_TEXT = __HTML_REPR__

SYSTEM_PROMPTS = __PROMPTS_REPR__


def _json_response(status, obj):
    return {
        "isBase64Encoded": False,
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
        "body": json.dumps(obj, ensure_ascii=False),
    }


def _html_response():
    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache"},
        "body": HTML_TEXT,
    }


def _config():
    # 环境变量类型校验：非数字一律回退默认，避免请求时崩溃
    def _int_env(name, default):
        try:
            return int(os.environ.get(name) or default)
        except (TypeError, ValueError):
            return default
    def _float_env(name, default):
        try:
            return float(os.environ.get(name) or default)
        except (TypeError, ValueError):
            return default
    def _clean(name):
        val = (os.environ.get(name) or "").strip()
        if not val or "粘贴" in val or val.startswith("在这里"):
            return ""
        return val
    # 多 API 支持：最多 3 组，组 1 兼容旧变量 API_KEY / API_BASE_URL / API_MODEL
    providers = []
    k1 = _clean("API_KEY_1") or _clean("API_KEY")
    if k1:
        providers.append({
            "id": "1",
            "api_key": k1,
            "base_url": _clean("API_BASE_URL_1") or _clean("API_BASE_URL") or "https://api.deepseek.com/v1/chat/completions",
            "model": _clean("API_MODEL_1") or _clean("API_MODEL") or "deepseek-chat",
            "label": _clean("API_NAME_1") or _clean("API_MODEL_1") or _clean("API_MODEL") or "deepseek-chat",
        })
    for i in (2, 3):
        k = _clean("API_KEY_%d" % i)
        if not k:
            continue
        providers.append({
            "id": str(i),
            "api_key": k,
            "base_url": _clean("API_BASE_URL_%d" % i) or "https://api.deepseek.com/v1/chat/completions",
            "model": _clean("API_MODEL_%d" % i) or "deepseek-chat",
            "label": _clean("API_NAME_%d" % i) or _clean("API_MODEL_%d" % i) or "deepseek-chat",
        })
    return {
        "providers": providers,
        "temperature": _float_env("TEMPERATURE", 0.7),
        "max_history": _int_env("MAX_HISTORY", 20),
    }


def _call_api(prov, temperature, messages):
    body = {
        "model": prov["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    req = urllib.request.Request(
        prov["base_url"],
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + prov["api_key"]},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("API_HTTP_%s: %s" % (exc.code, detail[:400])) from exc
    except OSError as exc:   # 覆盖 URLError / socket.timeout / 连接被重置
        reason = getattr(exc, "reason", None) or exc
        raise RuntimeError("API_NETWORK: %s" % reason) from exc
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("API_BAD_RESPONSE: %s" % json.dumps(data, ensure_ascii=False)[:400]) from exc


def _clean_history(history, max_history):
    """只保留 user/assistant 消息，丢弃注入的 system 等其他 role；content 为字符串或数组（多模态）原样保留。"""
    cleaned = []
    for m in history[-max_history:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        if content is None:
            continue
        if isinstance(content, (str, list)):
            cleaned.append({"role": role, "content": content})
        else:
            cleaned.append({"role": role, "content": str(content)})
    return cleaned


def main_handler(event, context):
    path = event.get("path") or "/"
    method = event.get("httpMethod") or "GET"
    if path in ("/", "/index.html") and method == "GET":
        return _html_response()
    if path == "/api/status" and method == "GET":
        cfg = _config()
        providers = cfg["providers"]
        return _json_response(200, {
            "ready": bool(providers),
            "provider": providers[0]["label"] if providers else "",
            "model": providers[0]["model"] if providers else "",
            "providers": [{"id": p["id"], "model": p["model"], "label": p["label"]} for p in providers],
            "config_source": "SCF 环境变量",
        })
    if path == "/api/chat" and method == "POST":
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            try:
                import base64
                raw = base64.b64decode(raw).decode("utf-8")
            except Exception as exc:
                return _json_response(400, {"error": "BAD_REQUEST", "message": "body 解码失败"})
        try:
            req = json.loads(raw.lstrip("\\ufeff"))
        except (ValueError, json.JSONDecodeError) as exc:
            return _json_response(400, {"error": "BAD_REQUEST", "message": "请求体不是合法 JSON"})
        mode = req.get("mode", "work")
        if mode not in ("work", "emotion"):
            mode = "work"
        history = req.get("messages", [])
        if not isinstance(history, list):
            return _json_response(400, {"error": "BAD_REQUEST", "message": "messages 必须是数组"})
        cfg = _config()
        providers = cfg["providers"]
        if not providers:
            return _json_response(503, {"error": "NO_API_KEY", "message": "云函数环境变量未配置 API Key（API_KEY 或 API_KEY_1~API_KEY_3），请到 SCF 控制台配置"})
        system = {"role": "system", "content": SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["work"])}
        max_history = max(1, min(cfg["max_history"], 60))
        messages = [system] + _clean_history(history, max_history)
        # 前端可指定 provider（"1"/"2"/"3"）；不指定则按顺序自动尝试，失败自动切下一组
        want = str(req.get("provider", "") or "").strip()
        candidates = [p for p in providers if p["id"] == want] if want else providers
        try_list = candidates or providers
        last = None
        for p in try_list:
            try:
                reply = _call_api(p, cfg["temperature"], messages)
                return _json_response(200, {
                    "reply": reply,
                    "provider": {"id": p["id"], "model": p["model"], "label": p["label"]},
                })
            except RuntimeError as exc:
                last = {"id": p["id"], "detail": str(exc)}
        return _json_response(502, {
            "error": "API_ALL_FAILED",
            "message": (last and last["detail"]) or "所有模型均调用失败",
            "provider": last and {"id": last["id"]},
            "tried": [p["id"] for p in try_list],
        })
    return _json_response(404, {"error": "NOT_FOUND", "message": "路径不存在"})


if __name__ == "__main__":
    import sys
    print("SCF handler OK; run via Tencent Cloud SCF console")
'''

PROMPTS_FILE = BASE.parent / "prompts.json"
try:
    prompts = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
except (json.JSONDecodeError, OSError) as exc:
    raise SystemExit("缺少或损坏 prompts.json（提示词单一来源）：%s" % exc)
if not isinstance(prompts, dict) or not prompts.get("work") or not prompts.get("emotion"):
    raise SystemExit("prompts.json 必须包含 work 和 emotion 两段提示词")

code = handler_code.replace("__HTML_REPR__", repr(HTML)).replace("__PROMPTS_REPR__", repr(prompts))
SRC.write_text(code, encoding="utf-8")
print("written:", SRC)
print("bytes:", SRC.stat().st_size)
