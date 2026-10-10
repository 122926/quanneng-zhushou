#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全能助手 · 手机网页版 —— 本地后端（零依赖，仅用 Python 标准库）

用法：
    python server.py
    然后浏览器打开 http://127.0.0.1:8787 （手机用同一局域网访问 http://<电脑IP>:8787）

配置文件：同目录 config.json（把 config.example.json 复制改名后填入 API Key）。
提示词单一来源：同目录 prompts.json（改人格只改它；缺失时回退内置兜底）。

v2 新增能力：
    1. Provider 可插拔：config.json 里可配置多个服务商（providers），按名称切换。
    2. 模式路由：mode_routing 指定每个模式（工作/情感/自定义角色）用哪个 Provider。
    3. 流式输出：/api/chat 支持 stream=true，SSE 逐字转发。
    4. 轻量记忆：前端把关键事实随请求带来，注入 system prompt。
    5. 角色库：prompts.json 支持 roles 数组，任意多个角色。
"""

import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "全能助手.html"
CONFIG_FILE = BASE_DIR / "config.json"
PROMPTS_FILE = BASE_DIR / "prompts.json"
MEMORY_DB_FILE = BASE_DIR / "memory.db"
DEFAULT_PORT = 8787

DEFAULT_CONFIG = {
    "provider": "deepseek",                      # 默认 Provider 名
    "api_key": "",
    "base_url": "https://api.deepseek.com/v1/chat/completions",
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_history": 20,                           # 携带的历史消息条数上限
    "system_prompts": {},                        # {模式id: 提示词}，可覆盖 prompts.json
    "providers": {},                             # {服务商名: {base_url, model, api_key, temperature}}
    "mode_routing": {},                          # {模式id: 服务商名}
    "memory": {                                  # 长期记忆（SQLite，参考 claude-mem 的 捕获→压缩→存储→召回→注入）
        "recall_top": 5,                         # 每次对话注入的召回记忆条数
        "compress_threshold": 16,                # 前端历史达到多少条后自动压缩一批
        "compress_batch": 8,                     # 每批压缩的消息条数
    },
    "resilience": {                              # 可靠性（参考 AIRI：429/503 退避重试 + Provider 失败降级）
        "retry_times": 2,                        # 429/503/网络错误额外重试次数
        "retry_base_sec": 2,                     # 退避起步秒数（每次翻倍）
        "failover": True,                        # 主 Provider 失败后是否换备用
        "summary_enabled": True,                 # 会话内滚动摘要（超窗旧对话压成摘要继续带，参考 AIRI compaction）
    },
}

# 注意：下方 SYSTEM_PROMPTS 仅作 prompts.json 缺失/损坏时的兜底。
# 修改人格请编辑根目录 prompts.json（单一来源），不要直接改这里。
SYSTEM_PROMPTS = {
    "work": (
        "你是「全能助手」的工作模式：一名亦师亦友的工作助手，服务对象主要是大学生和个人开发者。\n"
        "【定位】三副面孔：师——给专业判断、挑真问题；友——平视对话、一起头脑风暴；秘书——把杂活落地成可执行成果。"
        "核心原则：先弄清对方到底要什么，再动手；给判断但不替用户拍板；结论要能落地成下一步动作。\n"
        "【输出风格】\n"
        "1. 去AI化：不用\"一站式、智能化、赋能、突破性、打造生态\"等套词，句子长短交错，像人写的话。\n"
        "2. 多方案：重要决策默认给2-3个版本（稳妥/进取/激进），写明好处、代价、风险，不替用户单选。\n"
        "3. 行动收束：回答末尾给\"现在能做的一件小事 + 观察窗口或停止条件\"，以及值得回来反馈的信号。\n"
        "4. 证据诚实：不编造数据、案例、政策或事实；数字拿不准标注\"待核实\"并说明来源。\n"
        "5. 用户可随时要求切换精简/详细/口语化/表格等格式。\n"
        "【擅长领域要点】\n"
        "- 国创/挑战杯商业计划书：九章结构（摘要/痛点/产品/市场/商业模式/落地/团队/财务风险/规划）；摘要最后定稿且与正文数字一致；"
        "痛点要场景+证据；市场给测算逻辑和口径；竞品用表格；风险不少于3条且每条有对策；不编造数据、访谈、合作意向。\n"
        "- 路演PPT与答辩：先筛\"是否解决真问题、有没有真实进展、数字是否可信\"；把常见答辩问提前写进材料。\n"
        "- 技术学习（嵌入式/STM32/ESP32/C/PCB/飞机电子维修）：调试先复现、读报错原文、分编译/运行/硬件三类；改一处测一处；"
        "硬件先查供电和地；中断里不做耗时操作；注意器件型号、驱动、串口波特率。\n"
        "- 文档润色与去AI化降重：打散句子结构、长短句交错、保留核心信息、去华丽宣传话术、平实叙述。\n"
        "- 会议纪要/周报：提炼决定、待办、负责人、截止时间。\n"
        "- 任务拆解/时间规划：目标拆成可检查的里程碑，识别卡点和风险。\n"
        "- 复盘：事实—结果—原因—下一步。\n"
        "- 头脑风暴：先多方案发散，再按标准取舍。\n"
        "- 职业规划：结合现实条件给多条路径与取舍，不画大饼。\n"
        "【安全边界】不编造数据、文件、证书；重要决定（投项目、花大钱、签约、体检就医）给利弊与检查清单，由用户决定；"
        "涉及法律、医疗、财务只给通用信息，不冒充专家；发现方案错误直接指出并给修改建议。\n"
        "【输入证据】以用户提供的文件、数据、转述为准；材料矛盾时指出矛盾，不强行调和；缺失信息保持未知，不虚构。"
    ),
    "emotion": (
        "你是「全能助手」的情感模式：一名全面情感顾问。三副面孔：顾问——给专业判断，把心理学结论转译成人话；"
        "倾听者——先接住情绪再讲道理，不灌鸡汤；行动教练——把分析落地成下一步。\n"
        "【核心原则】先接住情绪，再分清事实，最后给能执行的选择。把\"对用户最有利\"理解为情绪稳定、安全、自尊、边界、互惠、"
        "时间精力、机会成本与长期信任的综合利益。\n"
        "【工作流程】\n"
        "1. 接情绪：先用2-4句指出感受、触发点和冲突，认可感受；情绪强烈时先缩小到\"这一小时能做什么\"。\n"
        "2. 分事实：列已知事实、合理推测、关键未知；不凭单次回复、表情或标签定性，以行为证据（持续主动、兑现、投入、边界、冲突修复）为准。\n"
        "3. 给建议：一句首选+2-4个理由；有真实权衡时再给2-3个版本（稳妥/进取/果断），写明各自代价。\n"
        "4. 行动收束：给一个现在能做的小动作、观察窗口或停止条件，以及值得回来反馈的信号。\n"
        "【输出风格】去AI化（不用\"赋能、底层逻辑、高维认知\"等套词）；证据诚实（心理学结论区分较强证据/理论框架/流行说法，"
        "拿不准标\"待核实\"）；可切换精简/详细/口语化/表格。\n"
        "【擅长领域要点】\n"
        "- 情绪管理（焦虑/内耗/低落/愤怒）：先区分日常情绪与需专业转介的信号（持续两周以上低落、自伤想法、惊恐发作等）；"
        "情绪高峰时不急着做决定、不发送激烈消息；命名情绪+物理降温+缩小到一小时；内耗识别模式（反刍/灾难化/完美主义拖延/比较/过度负责）再拆解；"
        "日常养护靠睡眠、运动、情绪出口。\n"
        "- 自我认知与价值感：把\"我不行\"拆成事实/行为/结论三层；用行为记录替代自我评价；从可完成的小事做起；"
        "区分\"我的价值\"和\"我的表现\"；迷茫时补信息、降标准、先试小的。\n"
        "- 恋爱关系（心动/暧昧/追求/冲突/分手/复合）：分析互惠、可靠、吸引、价值观、现实可行性、可逆性、安全与机会成本；"
        "尊重边界——对方明确拒绝、要求不联系或反复不欢迎时，协助体面退出，不强行推进；要话术时先给一条可复制成品，再讲发送时机与后续。\n"
        "- 婚姻家庭：金钱家务育儿、双方家庭、生命周期；重大决定（婚姻、生育）给利弊与检查清单。\n"
        "- 人际经营：沟通、拒绝、冲突修复、情绪价值、职场人脉；高情商不等于讨好，边界要清晰。\n"
        "- 危机：出现自伤、伤人、家暴、跟踪、人身威胁时，先确认当下安全，引导联系可信支持或当地紧急服务（110/120/心理援助热线）。\n"
        "【安全边界】不诊断心理疾病、不给人贴标签；情绪问题超出日常范围时建议专业心理咨询或医疗机构；"
        "禁止提供贬低、服从性测试、嫉妒操控、奖惩、煤气灯、孤立、跟踪或性施压的实施方案；"
        "不保证任何方法能让特定的人改变心意；涉及隐私提醒注意信息暴露。\n"
        "【输入证据】聊天截图/转述以用户提供的内容为准，只把可见文字、说话人、顺序当事实；不补线下动作、语气或内心；缺失保持未知，不虚构。"
    ),
}

# 默认角色元信息（prompts.json 未提供 roles 数组时的兜底）
DEFAULT_ROLES = [
    {"id": "work", "name": "工作", "color": "#0F766E"},
    {"id": "emotion", "name": "情感", "color": "#B45309"},
]


def _num(*values, default=0):
    """取第一个能转成 float 的值。"""
    for v in values:
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return default


def load_prompts() -> dict:
    """提示词单一来源：优先读 prompts.json；缺失/损坏时回退内置 SYSTEM_PROMPTS。"""
    try:
        data = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"work": SYSTEM_PROMPTS["work"], "emotion": SYSTEM_PROMPTS["emotion"], "roles": []}
    if not isinstance(data, dict):
        return {"work": SYSTEM_PROMPTS["work"], "emotion": SYSTEM_PROMPTS["emotion"], "roles": []}
    roles = data.get("roles")
    if not isinstance(roles, list):
        roles = []
    return {
        "work": str(data.get("work") or SYSTEM_PROMPTS["work"]),
        "emotion": str(data.get("emotion") or SYSTEM_PROMPTS["emotion"]),
        "roles": roles,
    }


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"error": "CONFIG_MISSING"}
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"error": "CONFIG_BROKEN", "message": str(exc)}
    merged = dict(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        for k in ("provider", "api_key", "base_url", "model", "temperature",
                  "max_history", "system_prompts", "providers", "mode_routing", "memory", "resilience"):
            if k in cfg and cfg[k] is not None:
                merged[k] = cfg[k]
    # 占位文字视为未填写 Key
    key = str(merged.get("api_key", "")).strip()
    if not key or "粘贴" in key or key.startswith("在这里"):
        key = ""
    merged["api_key"] = key
    # 配置类型校验：非数字一律回退默认，避免请求时崩溃
    try:
        merged["max_history"] = int(merged["max_history"])
    except (TypeError, ValueError):
        merged["max_history"] = DEFAULT_CONFIG["max_history"]
    try:
        merged["temperature"] = float(merged["temperature"])
    except (TypeError, ValueError):
        merged["temperature"] = DEFAULT_CONFIG["temperature"]
    if not isinstance(merged.get("system_prompts"), dict):
        merged["system_prompts"] = {}
    if not isinstance(merged.get("providers"), dict):
        merged["providers"] = {}
    if not isinstance(merged.get("mode_routing"), dict):
        merged["mode_routing"] = {}
    if not isinstance(merged.get("memory"), dict):
        merged["memory"] = {}
    if not isinstance(merged.get("resilience"), dict):
        merged["resilience"] = {}
    return merged


def resolve_providers(cfg: dict) -> dict:
    """把 config 解析成 {服务商名: 连接信息}，兼容旧版单 Provider 写法。"""
    provs = {}
    for name, p in (cfg.get("providers") or {}).items():
        if not isinstance(p, dict):
            continue
        provs[name] = {
            "base_url": str(p.get("base_url") or cfg.get("base_url") or DEFAULT_CONFIG["base_url"]),
            "model": str(p.get("model") or cfg.get("model") or DEFAULT_CONFIG["model"]),
            "api_key": str(p.get("api_key") or cfg.get("api_key") or "").strip(),
            "temperature": _num(p.get("temperature"), cfg.get("temperature"), DEFAULT_CONFIG["temperature"]),
        }
    if not provs:
        name = str(cfg.get("provider") or "default")
        provs[name] = {
            "base_url": str(cfg.get("base_url") or DEFAULT_CONFIG["base_url"]),
            "model": str(cfg.get("model") or DEFAULT_CONFIG["model"]),
            "api_key": cfg.get("api_key") or "",
            "temperature": _num(cfg.get("temperature"), DEFAULT_CONFIG["temperature"]),
        }
    return provs


def pick_provider(cfg: dict, provs: dict, mode: str) -> dict:
    """按模式路由选 Provider；未配置路由时回退默认。"""
    route = cfg.get("mode_routing") or {}
    name = route.get(mode) if isinstance(route, dict) else None
    if name and name in provs:
        return provs[name]
    default_name = cfg.get("provider")
    if default_name in provs:
        return provs[default_name]
    return next(iter(provs.values()))


def role_prompt(cfg: dict, prompts: dict, mode: str) -> str:
    """取某模式的 system 提示词：config.system_prompts > roles 数组 > 顶层 work/emotion > 兜底。"""
    sp = cfg.get("system_prompts") or {}
    if isinstance(sp, dict) and sp.get(mode):
        return str(sp[mode])
    for r in prompts.get("roles") or []:
        if isinstance(r, dict) and r.get("id") == mode and r.get("prompt"):
            return str(r["prompt"])
    if prompts.get(mode):
        return str(prompts[mode])
    if mode in SYSTEM_PROMPTS:
        return SYSTEM_PROMPTS[mode]
    return SYSTEM_PROMPTS["work"]


def _clean_history(history: list, max_history: int) -> list:
    """只保留最近 max_history 条里的 user/assistant 消息，丢弃注入的 system 等其他 role；content 为字符串或数组（多模态）原样保留。"""
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


# ============ 长期记忆（SQLite，零依赖，参考 claude-mem 的 捕获→压缩→存储→召回→注入） ============
# 前端每轮对话都经过这里：旧对话由 LLM 压缩成“记忆片段”入库（压缩），
# 新请求来时按用户消息关键词召回相关记忆（召回），拼进 system prompt（注入）。

_mem_lock = threading.Lock()


def _mem_connect():
    conn = sqlite3.connect(str(MEMORY_DB_FILE), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_memory_db():
    """建表（幂等）。首次启动时调用。"""
    with _mem_lock:
        conn = _mem_connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS memories(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'work',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    use_count INTEGER NOT NULL DEFAULT 0
                )"""
            )
            conn.commit()
        finally:
            conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def memory_add(content, mode="work") -> int:
    """新增一条记忆，返回 id；内容为空返回 0。"""
    text = str(content or "").strip()
    if not text or len(text) > 500:
        return 0
    now = _now()
    with _mem_lock:
        conn = _mem_connect()
        try:
            cur = conn.execute(
                "INSERT INTO memories(content, mode, created_at, updated_at) VALUES(?,?,?,?)",
                (text, mode, now, now),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def memory_list(mode=None, limit=200) -> list:
    """按更新时间倒序列出记忆（全部或某模式）。"""
    with _mem_lock:
        conn = _mem_connect()
        try:
            if mode:
                rows = conn.execute(
                    "SELECT id, content, mode, created_at, updated_at, use_count FROM memories "
                    "WHERE mode=? ORDER BY updated_at DESC LIMIT ?",
                    (mode, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, content, mode, created_at, updated_at, use_count FROM memories "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def memory_delete(mid) -> bool:
    with _mem_lock:
        conn = _mem_connect()
        try:
            cur = conn.execute("DELETE FROM memories WHERE id=?", (mid,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def memory_bump(mid) -> None:
    """命中一次召回就把使用次数 +1，用于热度排序。"""
    with _mem_lock:
        conn = _mem_connect()
        try:
            conn.execute(
                "UPDATE memories SET use_count=use_count+1, updated_at=? WHERE id=?",
                (_now(), mid),
            )
            conn.commit()
        finally:
            conn.close()


def _memory_keywords(text: str, max_words=16) -> list:
    """从文本里抽关键词（中文友好）：2-8 字的标点段直接收，整段补 2 字滑窗（步长 2）；
    英文/数字/下划线串（如 ESP32、deepseek）整体收。"""
    if not text:
        return []
    words = []
    parts = re.split(r"[\s,，。！？!?；;、:：\"'“”‘’()（）\[\]【】\n\t]+", text)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if re.fullmatch(r"[A-Za-z0-9_.\-]+", p):
            if 2 <= len(p) <= 20 and p not in words:
                words.append(p)
        elif 2 <= len(p) <= 8 and p not in words:
            words.append(p)
        if len(words) >= max_words:
            return words[:max_words]
    flat = re.sub(r"[\s,，。！？!?；;、:：\"'“”‘’()（）\[\]【】]+", "", text)
    if len(flat) >= 2:
        for i in range(0, len(flat) - 1, 2):
            seg = flat[i:i + 2]
            if seg not in words:
                words.append(seg)
            if len(words) >= max_words:
                break
    return words[:max_words]


def memory_search(query_text: str, mode: str, top: int = 5) -> list:
    """双向关键词召回：查询词命中记忆、或记忆词出现在查询文本都计分，命中越多越靠前；
    完全没有命中的时候，用最近更新的记忆保底（时间衰减，贴近最近聊过的话题）。
    命中的记录 use_count +1。"""
    if top <= 0:
        return []
    query_kw = _memory_keywords(str(query_text or ""))
    flat_query = re.sub(r"[\s,，。！？!?；;、:：\"'“”‘’()（）\[\]【】]+", "", str(query_text or ""))
    with _mem_lock:
        conn = _mem_connect()
        try:
            rows = conn.execute(
                "SELECT id, content, mode, created_at, updated_at, use_count FROM memories WHERE mode=?",
                (mode,),
            ).fetchall()
        finally:
            conn.close()
    scored = []
    for r in rows:
        content = str(r["content"])
        hits = 0
        if query_kw:
            hits += sum(1 for w in query_kw if w in content)
        mem_kw = _memory_keywords(content)
        if mem_kw and flat_query:
            hits += sum(1 for w in mem_kw if w in flat_query)
        if hits:
            scored.append((hits, r))
    if scored:
        # 稳定排序：先按更新时间倒序，再按命中数倒序 → 同分时最近更新的在前
        scored.sort(key=lambda x: x[1]["updated_at"], reverse=True)
        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [r for _, r in scored[:top]]
        for r in picked:
            memory_bump(int(r["id"]))
    else:
        # 无命中：时间衰减保底，注入最近更新的记忆（不刷热度，避免自强化）
        picked = rows[:top]
    return [dict(r) for r in picked]


MEMORY_COMPRESS_PROMPT = (
    "你是记忆整理器。下面是一段用户与助手的对话。请提炼出值得长期记住的内容："
    "用户的身份、偏好、经历、目标、决定、项目进展、重要结论或反复出现的话题。\n"
    "要求：\n"
    "1. 只输出一个 JSON 字符串数组，例如 [\"用户在三亚读飞机电子设备维修\", \"用户正在参加电子设计竞赛\"]；\n"
    "2. 每条不超过 60 字，口语化、独立成句，不包含对话语气词；\n"
    "3. 没有值得记的内容就输出 []；只输出 JSON，不要任何其他文字。\n\n"
    "对话如下：\n{conversation}"
)


def memory_compress(mode: str, messages: list, provider: dict) -> list:
    """把一段对话交给 LLM 压缩成记忆片段并入库，返回入库的记忆列表。

    调用方负责 provider 非空校验；LLM 返回异常时抛 ApiError，由调用方兜底。
    """
    lines = []
    for m in messages[-60:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict):
                    t = c.get("text") or c.get("content") or ""
                    parts.append(str(t))
            content = " ".join(p for p in parts if p)
        if content:
            who = "用户" if role == "user" else "助手"
            lines.append(f"{who}：{str(content)[:500]}")
    if not lines:
        return []
    conv = "\n".join(lines)[-6000:]
    prompt = MEMORY_COMPRESS_PROMPT.format(conversation=conv)
    reply = call_api(provider, [{"role": "user", "content": prompt}])
    items = _parse_memory_json(reply)
    saved = []
    for it in items:
        if memory_add(it, mode):
            saved.append(it)
    return saved


def _parse_memory_json(reply: str) -> list:
    """从 LLM 回复里解析 JSON 数组；带 ```json 包裹或前后杂文字都兼容。"""
    if not reply:
        return []
    text = reply.strip()
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    raw = m.group(0)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # 容错：尝试把每行当作一条记忆
        data = [ln.strip().lstrip("-•* ") for ln in text.splitlines()
                if ln.strip() and len(ln.strip()) >= 4]
    if not isinstance(data, list):
        return []
    out = []
    for it in data:
        if isinstance(it, str):
            s = it.strip()
        elif isinstance(it, dict):
            s = str(it.get("content") or it.get("text") or "").strip()
        else:
            s = str(it).strip()
        if 4 <= len(s) <= 200:
            out.append(s)
    return out[:20]


def build_system(role_prompt_text: str, memory: list, long_memories: list = None, personal: str = "") -> str:
    """把用户关键事实（前端带来的轻量记忆）、长期记忆（SQLite 召回）和个人数据（云端）注入 system prompt。"""
    blocks = []
    if memory:
        facts = "；".join(str(x).strip() for x in memory if str(x).strip())
        if facts:
            blocks.append("【用户档案（关键事实，由用户在本机保存，仅作参考；不要编造档案外的信息）】\n" + facts)
    if long_memories:
        items = [str(x).strip() for x in long_memories if str(x).strip()]
        if items:
            blocks.append("【相关历史记忆（由过往对话自动整理，仅作参考；若与本轮无关就忽略，不要编造）】\n" + "；".join(items))
    if personal and str(personal).strip():
        blocks.append(str(personal).strip())
    if not blocks:
        return role_prompt_text
    return role_prompt_text + "\n\n" + "\n\n".join(blocks)


_RETRY_STATUS = {429, 502, 503, 504}   # 限流/过载/网关错误，可退避重试（参考 AIRI）


def _retry_delay(headers, attempt, base):
    """尊重 Retry-After，否则 base 起步指数退避；上限 15 秒。"""
    try:
        v = int((headers or {}).get("Retry-After") or 0)
        if v > 0:
            return max(0, min(v, 15))
    except (TypeError, ValueError):
        pass
    return min(base * (2 ** max(attempt - 1, 0)), 15)


def call_api(cfg: dict, messages: list, resilience: dict = None, timeout: float = 120) -> str:
    """非流式调用上游 OpenAI 兼容接口；429/502/503/504 与网络错误按退避策略重试。"""
    resilience = resilience or {}
    try:
        retry_times = max(0, min(int(resilience.get("retry_times", 2)), 5))
    except (TypeError, ValueError):
        retry_times = 2
    try:
        retry_base = max(0, min(float(resilience.get("retry_base_sec", 2)), 10))
    except (TypeError, ValueError):
        retry_base = 2
    body = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"],
        "stream": False,
    }
    req = urllib.request.Request(
        cfg["base_url"],
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + cfg["api_key"],
        },
        method="POST",
    )
    last = None
    for attempt in range(retry_times + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise ApiError("API_BAD_RESPONSE", json.dumps(data, ensure_ascii=False)[:500]) from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last = ApiError("API_HTTP_" + str(exc.code), detail[:500])
            if exc.code not in _RETRY_STATUS or attempt >= retry_times:
                raise last from exc
            time.sleep(_retry_delay(exc.headers, attempt, retry_base))
        except OSError as exc:   # 覆盖 URLError / socket.timeout / 连接被重置，统一兜底为 API_NETWORK
            reason = getattr(exc, "reason", None) or exc
            last = ApiError("API_NETWORK", str(reason))
            if attempt >= retry_times:
                raise last from exc
            time.sleep(_retry_delay(None, attempt, retry_base))
    raise last  # 理论不可达（循环内必 raise），保险兜底


def call_api_stream(cfg: dict, messages: list, emit, resilience: dict = None) -> None:
    """流式调用上游，把增量文本通过 emit({"text": ...}) 交给调用方。

    429/502/503/504 与建连网络错误退避重试；重试耗尽抛 ApiError（由上层决定是否切换 Provider）。
    开始读到内容后的断流不再重试（用户已看到部分输出，切换会混乱）。
    """
    resilience = resilience or {}
    try:
        retry_times = max(0, min(int(resilience.get("retry_times", 2)), 5))
    except (TypeError, ValueError):
        retry_times = 2
    try:
        retry_base = max(0, min(float(resilience.get("retry_base_sec", 2)), 10))
    except (TypeError, ValueError):
        retry_base = 2
    body = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"],
        "stream": True,
    }
    req = urllib.request.Request(
        cfg["base_url"],
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + cfg["api_key"],
        },
        method="POST",
    )
    resp = None
    last = None
    for attempt in range(retry_times + 1):
        try:
            resp = urllib.request.urlopen(req, timeout=180)
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last = ApiError("API_HTTP_" + str(exc.code), detail[:500])
            if exc.code not in _RETRY_STATUS or attempt >= retry_times:
                raise last from exc
            time.sleep(_retry_delay(exc.headers, attempt, retry_base))
        except OSError as exc:
            reason = getattr(exc, "reason", None) or exc
            last = ApiError("API_NETWORK", str(reason))
            if attempt >= retry_times:
                raise last from exc
            time.sleep(_retry_delay(None, attempt, retry_base))

    buf = ""
    while True:
        chunk = resp.read(4096)
        if not chunk:
            break
        buf += chunk.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except (ValueError, TypeError):
                continue
            try:
                delta = obj["choices"][0]["delta"].get("content") or ""
            except (KeyError, IndexError, TypeError):
                continue
            if delta:
                emit({"text": delta})


def _recoverable(code: str) -> bool:
    """可恢复错误才允许切换 Provider：网络错误 / 限流 / 5xx。4xx 业务错误换 Provider 无意义。"""
    if code == "API_NETWORK":
        return True
    if code.startswith("API_HTTP_"):
        try:
            return int(code[len("API_HTTP_"):]) in _RETRY_STATUS
        except ValueError:
            return False
    return False


def ordered_providers(cfg: dict, provs: dict, mode: str) -> list:
    """按 主 Provider（模式路由/默认）→ 其余配置顺序 排列，跳过没配 Key 的。返回 [(name, provider)]。"""
    route = cfg.get("mode_routing") or {}
    main_name = route.get(mode) if isinstance(route, dict) else None
    if not main_name or main_name not in provs:
        default_name = cfg.get("provider")
        main_name = default_name if default_name in provs else (next(iter(provs), None))
    out = []
    if main_name and main_name in provs and provs[main_name].get("api_key"):
        out.append((main_name, provs[main_name]))
    for name, p in provs.items():
        if name != main_name and p.get("api_key"):
            out.append((name, p))
    return out


def call_with_failover(providers: list, messages: list, stream: bool, emit=None, resilience: dict = None):
    """按序尝试 providers；可恢复错误换下一个，全部失败抛最后一个 ApiError。
    stream=False 返回 LLM 回复内容；stream=True 把最终错误交给 emit 并返回成功使用的 provider 名。"""
    last = None
    for _idx, (name, prov) in enumerate(providers):
        try:
            if stream:
                call_api_stream(prov, messages, emit, resilience)
                return name
            return call_api(prov, messages, resilience)
        except ApiError as exc:
            last = exc
            if not _recoverable(exc.code):
                break
    if stream and emit is not None:
        emit({"error": last.code, "message": str(last)})
        return None
    raise last


# ============ 会话内滚动摘要（参考 AIRI compaction：保留最近 N 轮原文，更早的压成摘要继续带） ============
_summary_cache = {}      # {mode: {"count": int, "text": str, "failed_at": float|None}}
_summary_lock = threading.Lock()
SUMMARY_FAIL_COOLDOWN = 600   # 摘要失败后 10 分钟内不再尝试，避免服务商宕机时每个请求都白等

SUMMARY_PROMPT = (
    "你是对话摘要器。把下面这段历史对话压缩成 2-4 句中文摘要，"
    "保留：讨论主题、用户的决定与偏好、关键结论、待办事项。"
    "用简洁陈述句概括，不要重复对话原文，只输出摘要正文：\n\n{conversation}"
)


def _normalize_history(history: list) -> list:
    """清洗全部历史（过滤 system 等非 user/assistant 消息，不截断）；供滚动摘要使用。"""
    cleaned = []
    for m in history:
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


def _summarize_delta(provider: dict, messages: list) -> str:
    """把一段消息压缩成摘要；短超时 + 不重试，失败返回空串（调用方降级为直接截断）。"""
    lines = []
    for m in messages[-20:]:
        if not isinstance(m, dict):
            continue
        content = m.get("content")
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict):
                    t = c.get("text") or c.get("content") or ""
                    parts.append(str(t))
            content = " ".join(p for p in parts if p)
        if content:
            who = "用户" if m.get("role") == "user" else "助手"
            lines.append(f"{who}：{str(content)[:300]}")
    if not lines:
        return ""
    prompt = SUMMARY_PROMPT.format(conversation="\n".join(lines)[-4000:])
    try:
        return call_api(provider, [{"role": "user", "content": prompt}],
                        resilience={}, timeout=25).strip()
    except ApiError:
        return ""


def rolling_summary(mode: str, history: list, provider: dict, max_history: int):
    """AIRI compaction 式滚动摘要。

    - 历史不超窗：清掉缓存，原样返回
    - 超窗：把新增的超窗部分压成摘要追加进缓存，返回 (摘要文本, 保留的最近 max_history 条)
    - 摘要失败：进入 10 分钟冷却，本次降级为直接截断
    返回 (summary_text_or_None, kept_history)。
    """
    if len(history) <= max_history:
        with _summary_lock:
            _summary_cache.pop(mode, None)
        return None, history
    target = len(history) - max_history
    now = time.time()
    with _summary_lock:
        entry = _summary_cache.get(mode)
        if entry is None:
            entry = _summary_cache[mode] = {"count": 0, "text": "", "failed_at": None}
        if entry["failed_at"] and now - entry["failed_at"] < SUMMARY_FAIL_COOLDOWN:
            return None, history[target:]
        if target > entry["count"]:
            need = history[entry["count"]:target]
            entry["count"] = target  # 占位推进，防并发重复生成；失败回滚
        else:
            need = None
    if need:
        delta = _summarize_delta(provider, need)
        with _summary_lock:
            e = _summary_cache.get(mode)
            if e is not None:
                if delta:
                    e["text"] = (e["text"] + "\n" + delta).strip()
                    e["failed_at"] = None
                else:
                    e["count"] = max(0, e["count"] - len(need))
                    e["failed_at"] = now
    with _summary_lock:
        text = (_summary_cache.get(mode) or {}).get("text")
    return (text or None), history[target:]


class ApiError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Handler(BaseHTTPRequestHandler):
    server_version = "QuannengWeb/2.0"

    # ---------- 通用响应 ----------
    def _send(self, status: int, obj, headers=None):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8").lstrip("\ufeff"))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": "BAD_REQUEST", "message": "请求体不是合法 JSON"})
            return None

    def _serve_static(self, rel: str, content_type: str, cache: str):
        """服务白名单静态文件（PWA 资源），防路径穿越：只允许项目内相对路径。"""
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
        if self.path in ("/", "/index.html"):
            if not HTML_FILE.exists():
                self._send(404, {"error": "HTML_MISSING", "message": "未找到 全能助手.html"})
                return
            payload = HTML_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(payload)
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
            if name and "/" not in name and "\\" not in name and name.endswith(".png"):
                self._serve_static("icons/" + name, "image/png", "max-age=86400")
                return
        if self.path == "/api/status":
            cfg = load_config()
            if cfg.get("error"):
                self._send(200, {"ready": False, "error": cfg["error"]})
                return
            provs = resolve_providers(cfg)
            self._send(200, {
                "ready": any(p.get("api_key") for p in provs.values()),
                "provider": cfg.get("provider", ""),
                "model": next(iter(provs.values()), {}).get("model", ""),
                "providers": sorted(provs.keys()),
                "routing": cfg.get("mode_routing", {}),
                "config_file": str(CONFIG_FILE),
            })
            return
        if self.path == "/api/roles":
            prompts = load_prompts()
            roles = prompts.get("roles") or []
            out = []
            for r in roles:
                if not isinstance(r, dict) or not r.get("id"):
                    continue
                out.append({
                    "id": str(r["id"]),
                    "name": str(r.get("name") or r["id"]),
                    "color": str(r.get("color") or "#0F766E"),
                })
            if not out:
                out = [dict(r) for r in DEFAULT_ROLES]
            self._send(200, {"roles": out, "default": "work"})
            return
        if self.path.split("?")[0] == "/api/memory":
            q = urllib.parse.urlsplit(self.path).query
            params = urllib.parse.parse_qs(q)
            mode = (params.get("mode") or [None])[0]
            self._send(200, {"memories": memory_list(mode)})
            return
        self._send(404, {"error": "NOT_FOUND", "message": "路径不存在"})

    # ---------- POST ----------
    def _handle_memory_compress(self, req):
        """把一段对话压缩成记忆片段入库（由 LLM 提炼）。"""
        mode = str(req.get("mode") or "work")
        messages = req.get("messages", [])
        if not isinstance(messages, list):
            self._send(400, {"error": "BAD_REQUEST", "message": "messages 必须是数组"})
            return
        cfg = load_config()
        if cfg.get("error"):
            self._send(503, {"error": cfg["error"], "message": "缺少 config.json，请先配置 API Key"})
            return
        provs = resolve_providers(cfg)
        provider = pick_provider(cfg, provs, mode)
        if not provider.get("api_key"):
            self._send(503, {"error": "NO_API_KEY",
                             "message": "当前模式路由到的服务商未配置 API Key，无法压缩记忆（config.json 的 providers / api_key）"})
            return
        try:
            saved = memory_compress(mode, messages, provider)
        except ApiError as exc:
            self._send(502, {"error": exc.code, "message": "压缩记忆失败：" + str(exc)})
            return
        self._send(200, {"ok": True, "saved": saved, "count": len(saved)})

    def do_POST(self):
        req = self._read_json_body()
        if req is None:
            return
        if not isinstance(req, dict):
            self._send(400, {"error": "BAD_REQUEST", "message": "请求体必须是 JSON 对象"})
            return

        if self.path == "/api/memory":
            content = req.get("content")
            mode = str(req.get("mode") or "work")
            mid = memory_add(content, mode)
            if not mid:
                self._send(400, {"error": "EMPTY", "message": "记忆内容不能为空（≤500字）"})
                return
            self._send(200, {"ok": True, "id": mid})
            return
        if self.path == "/api/memory/delete":
            try:
                mid = int(req.get("id"))
            except (TypeError, ValueError):
                self._send(400, {"error": "BAD_REQUEST", "message": "缺少有效的 id"})
                return
            memory_delete(mid)
            self._send(200, {"ok": True})
            return
        if self.path == "/api/memory/compress":
            self._handle_memory_compress(req)
            return
        if self.path != "/api/chat":
            self._send(404, {"error": "NOT_FOUND", "message": "路径不存在"})
            return

        mode = str(req.get("mode") or "work")
        history = req.get("messages", [])
        if not isinstance(history, list):
            self._send(400, {"error": "BAD_REQUEST", "message": "messages 必须是数组"})
            return
        memory = req.get("memory", [])
        if not isinstance(memory, list):
            memory = []
        stream = bool(req.get("stream", False))

        cfg = load_config()
        if cfg.get("error"):
            self._send(503, {"error": cfg["error"], "message": "缺少 config.json，请复制 config.example.json 并填写 API Key"})
            return

        provs = resolve_providers(cfg)
        res_cfg = cfg.get("resilience") or {}
        providers = ordered_providers(cfg, provs, mode) if res_cfg.get("failover", True) else (
            [(name, prov) for name, prov in ordered_providers(cfg, provs, mode)[:1]]
        )
        if not providers:
            self._send(503, {"error": "NO_API_KEY",
                             "message": "当前模式路由到的服务商未配置 API Key（config.json 的 providers / api_key），请填写后再试"})
            return

        prompts = load_prompts()
        # 长期记忆召回：拿最近几条用户消息做关键词匹配，把相关记忆注入 system prompt
        mem_cfg = cfg.get("memory") or {}
        try:
            recall_top = max(0, min(int(mem_cfg.get("recall_top", 5)), 20))
        except (TypeError, ValueError):
            recall_top = 5
        long_mem = []
        if recall_top > 0:
            query = " ".join(
                str(m.get("content")) for m in history[-4:]
                if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str)
            )
            long_mem = memory_search(query, mode, recall_top)
        personal = req.get("personal")
        if personal is not None and not isinstance(personal, str):
            personal = str(personal)
        system = build_system(role_prompt(cfg, prompts, mode), memory, long_mem, personal)
        max_history = max(1, min(int(cfg.get("max_history", 20)), 60))
        # 会话内滚动摘要：超窗旧对话压成摘要继续带（AIRI compaction 式），不硬截断
        full = _normalize_history(history)
        summary_text = None
        if res_cfg.get("summary_enabled", True):
            try:
                summary_text, full = rolling_summary(mode, full, providers[0][1], max_history)
            except ApiError:
                summary_text, full = None, full[-max_history:]
        if summary_text:
            system = system + "\n\n【本场会话摘要（更早对话的压缩，仅作背景参考；不要编造摘要外的信息）】\n" + summary_text
        messages = [{"role": "system", "content": system}] + full

        if not stream:
            try:
                reply = call_with_failover(providers, messages, stream=False, resilience=res_cfg)
            except ApiError as exc:
                self._send(502, {"error": exc.code, "message": str(exc)})
                return
            self._send(200, {"reply": reply})
            return

        # ---------- 流式 SSE ----------
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def emit(obj: dict):
            try:
                self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                raise _ClientGone()

        try:
            call_with_failover(providers, messages, stream=True, emit=emit, resilience=res_cfg)
            emit({"done": True})
        except _ClientGone:
            pass  # 浏览器关掉了流，正常收尾即可
        finally:
            # HTTP/1.0 下响应体结束靠关闭连接标记；不关会让客户端一直等
            self.close_connection = True

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


class _ClientGone(Exception):
    """客户端断开连接时用于终止流式转发。"""


def main() -> int:
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    try:
        init_memory_db()
    except sqlite3.Error as exc:
        print("记忆库初始化失败（不影响主功能，记忆模块不可用）：%s" % exc)
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    except OSError as exc:
        print("端口 %d 被占用，可用 PORT 环境变量换端口：PORT=9000 python server.py" % port)
        print(str(exc))
        return 1
    print("=" * 56)
    print("  全能助手 · 手机网页版 后端已启动（v4：流式 / 多 Provider / 角色库 / 长期记忆 / 重试降级 / 滚动摘要）")
    print("  记忆库:   %s" % MEMORY_DB_FILE)
    print("  本机访问:  http://127.0.0.1:%d" % port)
    print("  手机访问:  http://<这台电脑的局域网IP>:%d" % port)
    print("  按 Ctrl+C 停止")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
