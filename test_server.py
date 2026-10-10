# -*- coding: utf-8 -*-
"""全能助手 server.py 核心逻辑单元测试（零依赖，全部 mock 掉网络与时间等待）。

运行：python -m unittest test_server -v   或   python test_server.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402


def make_provider(name="main", key="sk-test"):
    return {"base_url": "https://x/v1/chat/completions", "model": "m", "api_key": key, "temperature": 0.7}


# ---------- 配置加载 ----------
class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._old = server.CONFIG_FILE
        server.CONFIG_FILE = Path(self.tmpdir) / "config.json"

    def tearDown(self):
        server.CONFIG_FILE = self._old
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, text):
        server.CONFIG_FILE.write_text(text, encoding="utf-8")

    def test_missing_config(self):
        self.assertEqual(server.load_config().get("error"), "CONFIG_MISSING")

    def test_broken_config(self):
        self._write("{not json")
        self.assertEqual(server.load_config().get("error"), "CONFIG_BROKEN")

    def test_default_resilience_when_absent(self):
        # 旧版 config 没有 resilience 也能跑：合并默认块
        self._write(json.dumps({"provider": "deepseek", "api_key": ""}))
        cfg = server.load_config()
        self.assertIn("resilience", cfg)
        self.assertTrue(cfg["resilience"].get("failover", True))
        self.assertEqual(cfg["resilience"].get("retry_times", 2), 2)

    def test_resilience_override(self):
        self._write(json.dumps({"api_key": "", "resilience": {"retry_times": 0, "failover": False}}))
        cfg = server.load_config()
        self.assertEqual(cfg["resilience"]["retry_times"], 0)
        self.assertFalse(cfg["resilience"]["failover"])

    def test_placeholder_key_cleared(self):
        self._write(json.dumps({"api_key": "在这里粘贴你的API Key"}))
        self.assertEqual(server.load_config()["api_key"], "")


# ---------- 记忆解析 ----------
class ParseMemoryJsonTest(unittest.TestCase):
    def test_plain_json(self):
        out = server._parse_memory_json('["用户喜欢喝茶", "用户在参加电赛"]')
        self.assertEqual(out, ["用户喜欢喝茶", "用户在参加电赛"])

    def test_fenced_json(self):
        out = server._parse_memory_json('好的，以下是：\n```json\n["用户在三亚"]\n```')
        self.assertEqual(out, ["用户在三亚"])

    def test_empty_and_garbage(self):
        self.assertEqual(server._parse_memory_json(""), [])
        self.assertEqual(server._parse_memory_json("[]"), [])
        self.assertEqual(server._parse_memory_json("没有可记内容"), [])

    def test_too_short_filtered(self):
        out = server._parse_memory_json('["ok", "这条长度足够能入库"]')
        self.assertEqual(out, ["这条长度足够能入库"])


# ---------- SQLite 记忆（用临时库） ----------
class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._old_db = server.MEMORY_DB_FILE
        server.MEMORY_DB_FILE = os.path.join(self.tmpdir, "mem.db")
        server.init_memory_db()

    def tearDown(self):
        server.MEMORY_DB_FILE = self._old_db
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_list_delete(self):
        mid = server.memory_add("用户在三亚学飞机维修", "work")
        self.assertGreater(mid, 0)
        self.assertEqual(len(server.memory_list()), 1)
        self.assertTrue(server.memory_delete(mid))
        self.assertEqual(len(server.memory_list()), 0)

    def test_empty_add_rejected(self):
        self.assertEqual(server.memory_add("   "), 0)
        self.assertEqual(server.memory_add("x" * 501), 0)

    def test_search_hits(self):
        server.memory_add("用户参加电子设计竞赛", "work")
        hits = server.memory_search("电赛", "work", 5)
        self.assertTrue(any("电子设计竞赛" in h["content"] for h in hits))

    def test_search_fallback_recent(self):
        server.memory_add("用户喜欢喝茶", "work")
        hits = server.memory_search("完全不相关的话题xyz", "work", 5)
        self.assertEqual(len(hits), 1)  # 无命中走最近保底

    def test_keywords(self):
        kw = server._memory_keywords("ESP32 与 STM32 开发")
        self.assertIn("ESP32", kw)
        self.assertIn("开发", kw)
        self.assertEqual(server._memory_keywords(""), [])


# ---------- 重试 ----------
class RetryTest(unittest.TestCase):
    def _http_error(self, code, headers=None, body=b'{"error":"x"}'):
        return urllib.error.HTTPError("https://x", code, "msg", headers, io.BytesIO(body))

    def _ok_resp(self, text="ok"):
        resp = mock.Mock()
        resp.read.return_value = json.dumps({"choices": [{"message": {"content": text}}]}).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp

    def test_retry_then_success(self):
        calls = []

        def fake_urlopen(req, timeout=120):
            calls.append(timeout)
            if len(calls) == 1:
                raise self._http_error(429, {"Retry-After": "1"})
            return self._ok_resp()

        with mock.patch.object(server.urllib.request, "urlopen", side_effect=fake_urlopen), \
             mock.patch.object(server.time, "sleep", return_value=None) as sl:
            out = server.call_api(make_provider(), [{"role": "user", "content": "hi"}],
                                  {"retry_times": 2, "retry_base_sec": 2})
        self.assertEqual(out, "ok")
        self.assertEqual(len(calls), 2)
        sl.assert_called_once_with(1)  # Retry-After 优先于指数退避

    def test_400_no_retry(self):
        def fake_urlopen(req, timeout=120):
            raise self._http_error(400)

        with mock.patch.object(server.urllib.request, "urlopen", side_effect=fake_urlopen), \
             mock.patch.object(server.time, "sleep") as sl:
            with self.assertRaises(server.ApiError) as cm:
                server.call_api(make_provider(), [], {"retry_times": 2})
        self.assertTrue(cm.exception.code.startswith("API_HTTP_400"))
        sl.assert_not_called()

    def test_network_error_exhausts(self):
        def fake_urlopen(req, timeout=120):
            raise OSError("connection reset")

        with mock.patch.object(server.urllib.request, "urlopen", side_effect=fake_urlopen), \
             mock.patch.object(server.time, "sleep", return_value=None):
            with self.assertRaises(server.ApiError) as cm:
                server.call_api(make_provider(), [], {"retry_times": 1, "retry_base_sec": 0})
        self.assertEqual(cm.exception.code, "API_NETWORK")

    def test_retry_delay(self):
        self.assertEqual(server._retry_delay({"Retry-After": "3"}, 0, 2), 3)
        self.assertEqual(server._retry_delay({"Retry-After": "99"}, 0, 2), 15)  # 封顶
        self.assertLessEqual(server._retry_delay(None, 0, 2), 2)   # 指数：2^0
        self.assertLessEqual(server._retry_delay(None, 2, 2), 8)   # 指数：2^2
        self.assertLessEqual(server._retry_delay(None, 9, 2), 15)  # 封顶


# ---------- Provider 降级 ----------
class FailoverTest(unittest.TestCase):
    def test_fallback_on_recoverable(self):
        provs = [("main", make_provider()), ("backup", make_provider(key="sk2"))]
        with mock.patch.object(server, "call_api", side_effect=[
                server.ApiError("API_HTTP_503", "busy"),
                "from backup",
        ]):
            reply = server.call_with_failover(provs, [], stream=False)
        self.assertEqual(reply, "from backup")  # 非流式返回回复内容

    def test_4xx_stops_failover(self):
        provs = [("main", make_provider()), ("backup", make_provider(key="sk2"))]
        with mock.patch.object(server, "call_api", side_effect=server.ApiError("API_HTTP_400", "bad")):
            with self.assertRaises(server.ApiError):
                server.call_with_failover(provs, [], stream=False)

    def test_all_fail_raises_last(self):
        provs = [("main", make_provider()), ("backup", make_provider(key="sk2"))]
        with mock.patch.object(server, "call_api", side_effect=[
                server.ApiError("API_HTTP_503", "busy"),
                server.ApiError("API_NETWORK", "down"),
        ]):
            with self.assertRaises(server.ApiError) as cm:
                server.call_with_failover(provs, [], stream=False)
        self.assertEqual(cm.exception.code, "API_NETWORK")

    def test_stream_fail_emits_error(self):
        provs = [("main", make_provider())]
        emitted = []
        with mock.patch.object(server, "call_api_stream", side_effect=server.ApiError("API_HTTP_503", "busy")):
            name = server.call_with_failover(provs, [], stream=True, emit=emitted.append)
        self.assertIsNone(name)
        self.assertEqual(emitted[0]["error"], "API_HTTP_503")

    def test_ordered_providers_main_first_skip_nokey(self):
        cfg = {"provider": "main", "mode_routing": {}}
        provs = {"main": make_provider(), "backup": make_provider(), "nokey": make_provider(key="")}
        out = server.ordered_providers(cfg, provs, "work")
        self.assertEqual([n for n, _ in out], ["main", "backup"])


# ---------- 滚动摘要 ----------
class SummaryTest(unittest.TestCase):
    def setUp(self):
        server._summary_cache.clear()

    def test_within_window_no_summary(self):
        hist = [{"role": "user", "content": "a"}] * 10
        s, kept = server.rolling_summary("work", hist, make_provider(), 20)
        self.assertIsNone(s)
        self.assertEqual(len(kept), 10)

    def test_overflow_compress(self):
        hist = [{"role": "user", "content": "第%d条" % i} for i in range(25)]
        with mock.patch.object(server, "_summarize_delta", return_value="早期聊了配置与记忆"):
            s, kept = server.rolling_summary("work", hist, make_provider(), 20)
        self.assertIn("早期", s)
        self.assertEqual(len(kept), 20)

    def test_incremental_only_new_part(self):
        hist = [{"role": "user", "content": "第%d条" % i} for i in range(25)]
        with mock.patch.object(server, "_summarize_delta", return_value="摘要A"):
            server.rolling_summary("work", hist, make_provider(), 20)
        hist2 = hist + [{"role": "user", "content": "x"}]
        with mock.patch.object(server, "_summarize_delta", return_value="摘要B") as md:
            s, kept = server.rolling_summary("work", hist2, make_provider(), 20)
        md.assert_called_once()  # 只补新增的超窗部分
        self.assertIn("摘要A", s)
        self.assertIn("摘要B", s)

    def test_fail_cooldown(self):
        hist = [{"role": "user", "content": "第%d条" % i} for i in range(25)]
        with mock.patch.object(server, "_summarize_delta", return_value=""):
            s, kept = server.rolling_summary("work", hist, make_provider(), 20)
        self.assertIsNone(s)
        self.assertEqual(len(kept), 20)
        # 冷却期内不再尝试，直接截断
        with mock.patch.object(server, "_summarize_delta") as md:
            s2, _ = server.rolling_summary("work", hist, make_provider(), 20)
        md.assert_not_called()
        self.assertIsNone(s2)

    def test_normalize_history(self):
        hist = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": [{"type": "text", "text": "多模态"}]},
        ]
        out = server._normalize_history(hist)
        self.assertEqual(len(out), 3)
        self.assertTrue(all(m["role"] in ("user", "assistant") for m in out))


# ---------- system 组装 ----------
class SystemBuildTest(unittest.TestCase):
    def test_injects_blocks(self):
        out = server.build_system("BASE", ["关键事实"], ["记忆A", "记忆B"])
        self.assertIn("BASE", out)
        self.assertIn("关键事实", out)
        self.assertIn("记忆A", out)

    def test_no_memory_returns_base(self):
        self.assertEqual(server.build_system("BASE", [], None), "BASE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
