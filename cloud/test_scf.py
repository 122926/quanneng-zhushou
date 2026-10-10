# -*- coding: utf-8 -*-
"""本地模拟 SCF API 网关事件，验证 scf_handler.py 路由。"""
import json
import os
import sys
import py_compile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 1) 语法检查
py_compile.compile(os.path.join(os.path.dirname(__file__), "scf_handler.py"), doraise=True)
print("PASS py_compile")

import scf_handler as h

def call(path, method="GET", body=None):
    event = {"path": path, "httpMethod": method, "headers": {}, "body": body or "", "isBase64Encoded": False}
    return h.main_handler(event, None)

# 2) GET / -> HTML
r = call("/")
assert r["statusCode"] == 200, r
assert "全能助手" in r["body"], "HTML 未包含应用名"
assert "<!DOCTYPE html>" in r["body"]
print("PASS GET / -> HTML (bytes=%d)" % len(r["body"].encode("utf-8")))

# 3) GET /index.html -> HTML
r = call("/index.html")
assert r["statusCode"] == 200 and "全能助手" in r["body"]
print("PASS GET /index.html")

# 4) GET /api/status（无 API_KEY 环境变量）
r = call("/api/status")
d = json.loads(r["body"])
assert r["statusCode"] == 200 and d["ready"] is False, d
assert d["config_source"] == "SCF 环境变量"
print("PASS GET /api/status ->", d)

# 5) POST /api/chat 无 key -> 503 NO_API_KEY
payload = json.dumps({"mode": "work", "messages": [{"role": "user", "content": "你好"}]}, ensure_ascii=False)
r = call("/api/chat", "POST", payload)
d = json.loads(r["body"])
assert r["statusCode"] == 503 and d["error"] == "NO_API_KEY", d
print("PASS POST /api/chat no-key ->", d["error"])

# 6) POST /api/chat 非法 JSON -> 400
r = call("/api/chat", "POST", "not json{{{")
assert r["statusCode"] == 400, r
print("PASS POST /api/chat bad-json -> 400")

# 7) POST /api/chat 非法 mode 不报错（回落 work）但无 key 仍 NO_API_KEY
payload = json.dumps({"mode": "zzz", "messages": []})
r = call("/api/chat", "POST", payload)
assert r["statusCode"] == 503, r
print("PASS POST /api/chat unknown-mode falls back")

# 8) 未知路径 -> 404
r = call("/nope")
assert r["statusCode"] == 404
print("PASS unknown path -> 404")

# 9) 环境变量有占位 key 时视为未配置（占位文字）
os.environ["API_KEY"] = "在这里粘贴你的API Key"
r = call("/api/status")
d = json.loads(r["body"])
assert d["ready"] is False, d
print("PASS placeholder key treated as unset")
os.environ.pop("API_KEY", None)

print("ALL SCF TESTS PASSED")
