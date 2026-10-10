# -*- coding: utf-8 -*-
"""给 server.py 打补丁：新增 PWA 静态资源白名单路由"""
import io

p = r'E:\git-library\quanneng-zhushou-web\server.py'
s = io.open(p, encoding='utf-8').read()

anchor1 = """    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8").lstrip("\\ufeff"))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": "BAD_REQUEST", "message": "请求体不是合法 JSON"})
            return None

    # ---------- GET ----------
    def do_GET(self):
        if self.path in ("/", "/index.html"):"""

replacement1 = """    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8").lstrip("\\ufeff"))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": "BAD_REQUEST", "message": "请求体不是合法 JSON"})
            return None

    def _serve_static(self, rel: str, content_type: str, cache: str):
        \"\"\"服务白名单静态文件（PWA 资源），防路径穿越：只允许项目内相对路径。\"\"\"
        target = (BASE_DIR / rel).resolve()
        if not target.is_file() or not str(target).startswith(str(BASE_DIR)):
            self._send(404, {"error": "NOT_FOUND", "message": "资源不存在"})
            return
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(payload)

    # ---------- GET ----------
    def do_GET(self):
        if self.path in ("/", "/index.html"):"""

assert anchor1 in s, "anchor1 not found"
s = s.replace(anchor1, replacement1, 1)

anchor2 = """            self.wfile.write(payload)
            return
        if self.path == "/api/status":"""

replacement2 = """            self.wfile.write(payload)
            return
        # PWA 静态资源（白名单）
        if self.path == "/manifest.webmanifest":
            self._serve_static("manifest.webmanifest", "application/manifest+json; charset=utf-8", "no-cache")
            return
        if self.path == "/sw.js":
            self._serve_static("sw.js", "application/javascript; charset=utf-8", "no-cache")
            return
        if self.path.startswith("/icons/") and self.path.count("/") == 2:
            name = self.path.split("/")[-1]
            if name and "/" not in name and "\\\\" not in name and name.endswith(".png"):
                self._serve_static("icons/" + name, "image/png", "max-age=86400")
                return
        if self.path == "/api/status":"""

assert anchor2 in s, "anchor2 not found"
s = s.replace(anchor2, replacement2, 1)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print("server.py patched OK")
