# -*- coding: utf-8 -*-
"""给 全能助手.html 打补丁：PWA meta + 直连云端模式 + SW 注册"""
import io

p = r'E:\git-library\quanneng-zhushou-web\全能助手.html'
s = io.open(p, encoding='utf-8').read()

def rep(old, new, tag):
    global s
    assert old in s, "anchor missing: " + tag
    s = s.replace(old, new, 1)

# ---------- Patch 1: head 加 PWA meta ----------
rep(
    '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\'%3E%3Crect width=\'24\' height=\'24\' rx=\'5\' fill=\'%230F766E\'/%3E%3Cpath d=\'M7 8.5h10M7 12h6M7 15.5h8\' stroke=\'white\' stroke-width=\'1.8\' stroke-linecap=\'round\'/%3E%3C/svg%3E">',
    '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\'%3E%3Crect width=\'24\' height=\'24\' rx=\'5\' fill=\'%230F766E\'/%3E%3Cpath d=\'M7 8.5h10M7 12h6M7 15.5h8\' stroke=\'white\' stroke-width=\'1.8\' stroke-linecap=\'round\'/%3E%3C/svg%3E">\n'
    '<link rel="manifest" href="/manifest.webmanifest">\n'
    '<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">\n'
    '<meta name="mobile-web-app-capable" content="yes">\n'
    '<meta name="apple-mobile-web-app-capable" content="yes">\n'
    '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
    '<meta name="apple-mobile-web-app-title" content="全能助手">',
    "head-pwa"
)

# ---------- Patch 2: 设置面板加直连模式区 ----------
rep(
    '      <h4>朗读回复</h4>',
    '      <h4>直连云端模式（APP 独立用）</h4>\n'
    '      <p class="desc">填入 Key 后，手机不依赖电脑后端、直接调用云端 API——把网页"添加到主屏幕"后就是独立 APP。不填则照常用局域网后端。Key 只存这台浏览器。</p>\n'
    '      <div style="display:flex;flex-direction:column;gap:8px;margin:10px 0;">\n'
    '        <input id="dcKey" type="password" placeholder="API Key（如 sk-...）" maxlength="200" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;background:var(--bg);">\n'
    '        <input id="dcUrl" type="text" placeholder="base_url（留空=DeepSeek）" maxlength="200" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;background:var(--bg);">\n'
    '        <input id="dcModel" type="text" placeholder="model（留空=deepseek-chat）" maxlength="80" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;background:var(--bg);">\n'
    '        <textarea id="dcPrompts" rows="3" placeholder=\'{"work":"...","emotion":"..."} 可选，覆盖直连人格；留空用内置\' style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:13px;font-family:inherit;background:var(--bg);resize:vertical;"></textarea>\n'
    '        <button id="dcSave" type="button" style="border:0;border-radius:10px;background:var(--accent);color:#fff;padding:11px;font-size:14px;font-weight:600;">保存直连配置</button>\n'
    '        <button id="dcClear" type="button" style="border:1px solid #F3D9D6;background:#FDF3F2;color:var(--danger);border-radius:10px;padding:10px;font-size:14px;">关闭直连（回到局域网后端）</button>\n'
    '      </div>\n'
    '      <div id="dcStatus" class="desc"></div>\n'
    '\n'
    '      <h4>朗读回复</h4>',
    "settings-direct"
)

# ---------- Patch 3: el 增加直连元素（并补上 v2 遗漏的 stProviders/stRouting/stConfig） ----------
rep(
    '    swSpeak: document.getElementById("swSpeak"),\n'
    '    memInput: document.getElementById("memInput"),\n'
    '    memAdd: document.getElementById("memAdd"),\n'
    '    memList: document.getElementById("memList")\n'
    '  };',
    '    swSpeak: document.getElementById("swSpeak"),\n'
    '    memInput: document.getElementById("memInput"),\n'
    '    memAdd: document.getElementById("memAdd"),\n'
    '    memList: document.getElementById("memList"),\n'
    '    stProviders: document.getElementById("stProviders"),\n'
    '    stRouting: document.getElementById("stRouting"),\n'
    '    stConfig: document.getElementById("stConfig"),\n'
    '    dcKey: document.getElementById("dcKey"),\n'
    '    dcUrl: document.getElementById("dcUrl"),\n'
    '    dcModel: document.getElementById("dcModel"),\n'
    '    dcPrompts: document.getElementById("dcPrompts"),\n'
    '    dcSave: document.getElementById("dcSave"),\n'
    '    dcClear: document.getElementById("dcClear"),\n'
    '    dcStatus: document.getElementById("dcStatus")\n'
    '  };',
    "el-direct"
)

# ---------- Patch 4: 插入直连相关函数（在发送函数之前） ----------
rep(
    '  /* ---------- 发送 ---------- */\n'
    '  function send(text) {',
    '''  /* ---------- 直连云端模式 ---------- */
  var DIRECT_KEY = "qnz_direct";
  var DIRECT_PROMPTS_KEY = "qnz_direct_prompts";
  var DEFAULT_DIRECT = { base_url: "https://api.deepseek.com/v1/chat/completions", model: "deepseek-chat", api_key: "" };
  var DIRECT_PROMPTS = {
    work: "你是「全能助手」的工作模式：亦师亦友的工作助手，服务对象主要是大学生和个人开发者。三副面孔：师（给专业判断、挑真问题）、友（平视对话）、秘书（把杂活落地成可执行成果）。核心原则：先弄清对方到底要什么再动手；给判断但不替用户拍板；结论要能落地成下一步动作。输出风格：去AI化（不用“一站式、智能化、赋能”等套词，句子长短交错）；重要决策默认给2-3个方案并写明代价；回答末尾给一个现在能做的小事和观察窗口；不编造数据，数字拿不准标“待核实”。擅长：国创/挑战杯BP（九章结构）、路演答辩、嵌入式/STM32/ESP32/C编程调试、文档去AI化降重、纪要周报、任务拆解、职业规划。安全边界：不编造数据文件证书；重大决定给利弊清单由用户决定；法律医疗财务只给通用信息。",
    emotion: "你是「全能助手」的情感模式：全面情感顾问。三副面孔：顾问（把心理学结论转译成人话）、倾听者（先接住情绪再讲道理，不灌鸡汤）、行动教练（把分析落地成下一步）。工作流程：先接住情绪（2-4句指出感受与触发点），再分事实（已知/推测/未知），给一句首选+理由，最后给一个现在能做的小动作和观察窗口。输出风格：去AI化；心理学结论区分较强证据/理论框架/流行说法，拿不准标“待核实”。边界：不诊断心理疾病、不贴标签；出现自伤伤人风险时引导联系专业渠道（110/120/心理援助热线）；不提供操控、PUA、煤气灯类方案；尊重边界，对方明确拒绝时协助体面退出。"
  };
  function loadDirect() {
    try {
      var d = JSON.parse(localStorage.getItem(DIRECT_KEY) || "null");
      if (!d || !d.api_key) return null;
      return {
        base_url: (d.base_url || DEFAULT_DIRECT.base_url),
        model: (d.model || DEFAULT_DIRECT.model),
        api_key: d.api_key
      };
    } catch (e) { return null; }
  }
  function saveDirect(d) { try { localStorage.setItem(DIRECT_KEY, JSON.stringify(d)); } catch (e) {} }
  function clearDirect() { try { localStorage.removeItem(DIRECT_KEY); } catch (e) {} }
  function loadDirectPrompts() {
    try {
      var p = JSON.parse(localStorage.getItem(DIRECT_PROMPTS_KEY) || "null");
      return (p && typeof p === "object") ? p : null;
    } catch (e) { return null; }
  }
  function buildDirectSystem(mode, memory) {
    var prompts = loadDirectPrompts();
    var base = (prompts && prompts[mode]) || DIRECT_PROMPTS[mode] || DIRECT_PROMPTS.work;
    if (!memory || !memory.length) return base;
    var facts = [];
    for (var i = 0; i < memory.length; i++) if (String(memory[i]).trim()) facts.push(String(memory[i]).trim());
    return facts.length ? base + "\\n\\n【用户档案（关键事实，本机保存，仅作参考；不要编造档案外的信息）】\\n" + facts.join("；") : base;
  }
  // 直连模式读取 OpenAI 兼容 SSE：data: {"choices":[{"delta":{"content":"..."}}]}
  function readOpenAIStream(res, onChunk) {
    return new Promise(function (resolve, reject) {
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var acc = "", text = "";
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) { resolve(text); return; }
          acc += decoder.decode(r.value, { stream: true });
          var idx;
          while ((idx = acc.indexOf("\\n\\n")) >= 0) {
            var block = acc.slice(0, idx);
            acc = acc.slice(idx + 2);
            var lines = block.split("\\n");
            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (line.indexOf("data:") !== 0) continue;
              var payload = line.slice(5).trim();
              if (!payload || payload === "[DONE]") continue;
              var obj;
              try { obj = JSON.parse(payload); } catch (e) { continue; }
              if (obj.error) { reject(new Error((obj.error.message || obj.error) || "API 错误")); return; }
              var delta = obj.choices && obj.choices[0] && obj.choices[0].delta && obj.choices[0].delta.content;
              if (delta) { text += delta; onChunk(delta); }
            }
          }
          return pump();
        }).catch(reject);
      }
      pump();
    });
  }
  function sendBackendRequest(body, typing) {
    return fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (res) {
      if (!res.ok) {
        return res.json().then(function (d) {
          throw new Error((d && d.message) || (d && d.error) || "请求失败");
        });
      }
      typing.remove();
      var aiWrap = appendMsgNode("ai", "");
      aiWrap.classList.add("streaming");
      var bubble = aiWrap.querySelector(".bubble");
      var accText = "";
      return readStream(res, function (chunk) {
        accText += chunk;
        bubble.innerHTML = md(accText);
        scrollBottom();
      });
    });
  }
  function sendDirectRequest(direct, mode, history, memory, typing) {
    var sys = buildDirectSystem(mode, memory);
    var messages = [{ role: "system", content: sys }];
    for (var i = 0; i < history.length; i++) {
      if (history[i].role === "user" || history[i].role === "assistant") messages.push(history[i]);
    }
    return fetch(direct.base_url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + direct.api_key
      },
      body: JSON.stringify({ model: direct.model, messages: messages, temperature: 0.7, stream: true })
    }).then(function (res) {
      if (!res.ok) {
        return res.json().then(function (d) {
          var m = (d && d.error && (d.error.message || d.error)) || (d && d.message) || ("HTTP " + res.status);
          throw new Error(m);
        }).catch(function () { throw new Error("HTTP " + res.status); });
      }
      typing.remove();
      var aiWrap = appendMsgNode("ai", "");
      aiWrap.classList.add("streaming");
      var bubble = aiWrap.querySelector(".bubble");
      var accText = "";
      return readOpenAIStream(res, function (delta) {
        accText += delta;
        bubble.innerHTML = md(accText);
        scrollBottom();
      });
    });
  }

  /* ---------- 发送 ---------- */
  function send(text) {''',
    "direct-funcs"
)

# ---------- Patch 5: send() 主体分流 ----------
rep(
    '''    var body = {
      mode: mode,
      messages: state.histories[mode],
      memory: loadMem(),
      stream: true
    };

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (res) {
      if (!res.ok) {
        return res.json().then(function (d) {
          throw new Error((d && d.message) || (d && d.error) || "请求失败");
        });
      }
      typing.remove();
      var aiWrap = appendMsgNode("ai", "");
      aiWrap.classList.add("streaming");
      var bubble = aiWrap.querySelector(".bubble");
      var accText = "";
      return readStream(res, function (chunk) {
        accText += chunk;
        bubble.innerHTML = md(accText);
        scrollBottom();
      }).then(function (fullText) {
        aiWrap.classList.remove("streaming");
        state.histories[mode].push({ role: "assistant", content: fullText });
        saveHist(mode);
        renderAll();
        if (loadSpeak()) speakText(fullText);
      });
    }).catch(function (err) {
      typing.remove();
      var msg = (err && err.message) ? err.message : "请求失败";
      if (/连不上|Failed to fetch|NetworkError/i.test(msg)) msg = "连不上后端：请确认 server.py 已在电脑上启动";
      showBanner(msg, "打开设置", function () { el.overlay.classList.add("show"); });
    }).finally(function () {
      state.busy = false;
      el.send.disabled = false;
      el.input.focus();
    });''',
    '''    var direct = loadDirect();
    var useDirect = !!(direct && direct.api_key);

    var reqPromise = useDirect
      ? sendDirectRequest(direct, mode, state.histories[mode], loadMem(), typing)
      : sendBackendRequest(body, typing);

    reqPromise.then(function (fullText) {
      state.histories[mode].push({ role: "assistant", content: fullText });
      saveHist(mode);
      renderAll();
      if (loadSpeak()) speakText(fullText);
    }).catch(function (err) {
      typing.remove();
      var msg = (err && err.message) ? err.message : "请求失败";
      if (/连不上|Failed to fetch|NetworkError|API_NETWORK/i.test(msg)) msg = "连不上服务：直连模式请检查 API Key 和网络；局域网后端请确认 server.py 已启动";
      showBanner(msg, "打开设置", function () { el.overlay.classList.add("show"); });
    }).finally(function () {
      state.busy = false;
      el.send.disabled = false;
      el.input.focus();
    });''',
    "send-branch"
)

# ---------- Patch 6: openSettings 填充直连字段 ----------
rep(
    '''    el.swSpeak.classList.toggle("on", loadSpeak());
    el.swSpeak.setAttribute("aria-checked", String(loadSpeak()));
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (s) {''',
    '''    el.swSpeak.classList.toggle("on", loadSpeak());
    el.swSpeak.setAttribute("aria-checked", String(loadSpeak()));
    var dc = loadDirect();
    el.dcKey.value = dc ? dc.api_key : "";
    el.dcUrl.value = dc ? dc.base_url : "";
    el.dcModel.value = dc ? dc.model : "";
    var dp = loadDirectPrompts();
    el.dcPrompts.value = dp ? JSON.stringify(dp, null, 1) : "";
    el.dcStatus.textContent = dc ? "直连已启用：" + (dc.base_url || "") : "";
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (s) {''',
    "settings-fill"
)

# ---------- Patch 7: dcSave/dcClear 事件绑定 ----------
rep(
    '  el.speakBtn.addEventListener("click", speakLastReply);\n'
    '  document.getElementById("btnSettings").addEventListener("click", openSettings);',
    '  el.speakBtn.addEventListener("click", speakLastReply);\n'
    '  document.getElementById("btnSettings").addEventListener("click", openSettings);\n'
    '  el.dcSave.addEventListener("click", function () {\n'
    '    var key = el.dcKey.value.trim();\n'
    '    if (!key) { el.dcStatus.textContent = "请先填 API Key。"; return; }\n'
    '    saveDirect({\n'
    '      api_key: key,\n'
    '      base_url: el.dcUrl.value.trim() || DEFAULT_DIRECT.base_url,\n'
    '      model: el.dcModel.value.trim() || DEFAULT_DIRECT.model\n'
    '    });\n'
    '    var pv = el.dcPrompts.value.trim();\n'
    '    if (pv) {\n'
    '      try { saveDirectPrompts(JSON.parse(pv)); el.dcStatus.textContent = "直连已保存（含自定义人格）。"; }\n'
    '      catch (e) { el.dcStatus.textContent = "人格 JSON 格式不对，已忽略人格，其余已保存。"; }\n'
    '    } else {\n'
    '      try { localStorage.removeItem(DIRECT_PROMPTS_KEY); } catch (e) {}\n'
    '      el.dcStatus.textContent = "直连已保存（使用内置人格）。";\n'
    '    }\n'
    '  });\n'
    '  el.dcClear.addEventListener("click", function () {\n'
    '    clearDirect();\n'
    '    el.dcKey.value = ""; el.dcUrl.value = ""; el.dcModel.value = ""; el.dcPrompts.value = "";\n'
    '    el.dcStatus.textContent = "直连已关闭，将使用局域网后端。";\n'
    '  });',
    "dc-events"
)

# ---------- Patch 8: 启动时注册 Service Worker ----------
rep(
    '  /* ---------- 启动 ---------- */\n'
    '  initMic();',
    '  /* ---------- 启动 ---------- */\n'
    '  if ("serviceWorker" in navigator) {\n'
    '    navigator.serviceWorker.register("/sw.js").catch(function () { /* 不支持则静默 */ });\n'
    '  }\n'
    '  initMic();',
    "sw-register"
)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print("html patched OK, new size:", len(s))
