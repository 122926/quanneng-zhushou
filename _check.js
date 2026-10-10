
(function () {
  "use strict";

  var DEFAULT_ROLES = [
    { id: "work", name: "工作", color: "#0F766E" },
    { id: "emotion", name: "情感", color: "#B45309" }
  ];
  var MEM_KEY = "qnz_memory";
  var SPEAK_KEY = "qnz_speak";

  var state = {
    mode: "work",
    busy: false,
    roles: DEFAULT_ROLES.slice(),
    histories: {}
  };

  /* ---------- 存储 ---------- */
  function histKey(mode) { return "qnz_hist_" + mode; }
  function loadHist(mode) {
    try {
      var raw = localStorage.getItem(histKey(mode));
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr.slice(-100) : [];
    } catch (e) { return []; }
  }
  function saveHist(mode) {
    try {
      localStorage.setItem(histKey(mode), JSON.stringify((state.histories[mode] || []).slice(-100)));
    } catch (e) { /* 存储满时静默 */ }
  }
  function loadMem() {
    try {
      var a = JSON.parse(localStorage.getItem(MEM_KEY) || "[]");
      return Array.isArray(a) ? a : [];
    } catch (e) { return []; }
  }
  function saveMem(arr) {
    try { localStorage.setItem(MEM_KEY, JSON.stringify(arr.slice(-50))); } catch (e) {}
  }
  function loadSpeak() { return localStorage.getItem(SPEAK_KEY) === "1"; }
  function saveSpeak(on) {
    try { localStorage.setItem(SPEAK_KEY, on ? "1" : "0"); } catch (e) {}
  }

  var el = {
    main: document.getElementById("main"),
    messages: document.getElementById("messages"),
    welcome: document.getElementById("welcome"),
    input: document.getElementById("input"),
    send: document.getElementById("send"),
    banner: document.getElementById("banner"),
    bannerText: document.getElementById("bannerText"),
    bannerAct: document.getElementById("bannerAct"),
    tabs: document.getElementById("tabs"),
    cards: document.getElementById("cards"),
    brandMark: document.getElementById("brandMark"),
    mic: document.getElementById("btnMic"),
    speakBtn: document.getElementById("btnSpeak"),
    overlay: document.getElementById("overlay"),
    stReady: document.getElementById("stReady"),
    stProvider: document.getElementById("stProvider"),
    stModel: document.getElementById("stModel"),
    swSpeak: document.getElementById("swSpeak"),
    memInput: document.getElementById("memInput"),
    memAdd: document.getElementById("memAdd"),
    memList: document.getElementById("memList"),
    stProviders: document.getElementById("stProviders"),
    stRouting: document.getElementById("stRouting"),
    stConfig: document.getElementById("stConfig"),
    dcKey: document.getElementById("dcKey"),
    dcProvider: document.getElementById("dcProvider"),
    dcUrl: document.getElementById("dcUrl"),
    dcModel: document.getElementById("dcModel"),
    dcPrompts: document.getElementById("dcPrompts"),
    dcSave: document.getElementById("dcSave"),
    dcClear: document.getElementById("dcClear"),
    dcStatus: document.getElementById("dcStatus")
  };

  /* ---------- 基础工具 ---------- */
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  // 极简 Markdown：先转义防注入，再还原少量标记
  function md(src) {
    var blocks = [];
    var rest = String(src);
    var re = /```([\s\S]*?)```/g, m;
    while ((m = re.exec(rest)) !== null) {
      blocks.push({ start: m.index, end: re.lastIndex, html: "<pre><code>" + esc(m[1]) + "</code></pre>" });
    }
    var out = "", cursor = 0;
    blocks.forEach(function (b) {
      out += inlineMd(rest.slice(cursor, b.start));
      out += b.html;
      cursor = b.end;
    });
    out += inlineMd(rest.slice(cursor));
    return out;
  }
  function inlineMd(s) {
    var t = esc(s);
    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    var paras = t.split(/\n{2,}/);
    var html = paras.map(function (p) {
      var lines = p.split("\n");
      var buf = [];
      var inList = false;
      lines.forEach(function (line) {
        var lm = line.match(/^\s*[-*•]\s+(.*)$/);
        if (lm) {
          if (!inList) { buf.push("<ul>"); inList = true; }
          buf.push("<li>" + lm[1] + "</li>");
        } else {
          if (inList) { buf.push("</ul>"); inList = false; }
          buf.push(line.replace(/\n$/, "") ? line : "<br>");
        }
      });
      if (inList) { buf.push("</ul>"); }
      var body = buf.join("\n");
      if (/^\s*<ul>/.test(body) || /^\s*<pre>/.test(body) || /^\s*<br>/.test(body)) return body;
      return "<p>" + body.replace(/\n/g, "<br>") + "</p>";
    });
    return html.join("");
  }

  /* ---------- 角色 ---------- */
  function applyColor(color) {
    var c = /^#[0-9a-fA-F]{6}$/.test(color || "") ? color : "#0F766E";
    document.documentElement.style.setProperty("--accent", c);
    document.documentElement.style.setProperty("--accent-soft", c + "1A");
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", c);
  }
  function renderTabs(roles) {
    el.tabs.innerHTML = "";
    roles.forEach(function (r) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab";
      b.setAttribute("role", "tab");
      b.setAttribute("data-id", r.id);
      var dot = document.createElement("span");
      dot.className = "dot";
      dot.style.background = /^#[0-9a-fA-F]{6}$/.test(r.color) ? r.color : "";
      b.appendChild(dot);
      b.appendChild(document.createTextNode(r.name));
      b.addEventListener("click", function () { setMode(r.id); });
      el.tabs.appendChild(b);
    });
  }
  function renderCards(roles) {
    el.cards.innerHTML = "";
    var tags = {
      work: { tag: "师 · 友 · 秘书", desc: "商业计划书、路演答辩、嵌入式/编程辅导、文档去AI化、纪要周报、任务拆解、职业规划" },
      emotion: { tag: "顾问 · 倾听者 · 教练", desc: "情绪疏导、内耗焦虑、自我认知、恋爱关系、婚姻家庭、人际边界、危机转介" }
    };
    roles.slice(0, 2).forEach(function (r) {
      var info = tags[r.id] || { tag: "专属人格", desc: "切换到「" + r.name + "」人格开始对话" };
      var card = document.createElement("div");
      card.className = "card";
      card.setAttribute("role", "button");
      card.tabIndex = 0;
      card.setAttribute("aria-label", "切换到" + r.name + "模式");
      var go = function () { setMode(r.id); el.main.scrollTop = 0; };
      card.addEventListener("click", go);
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); }
      });
      var dot = /^#[0-9a-fA-F]{6}$/.test(r.color) ? r.color : "";
      card.innerHTML =
        '<span class="card-tag" style="color:' + dot + '"><span class="dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + dot + ';"></span>' +
        esc(r.name) + '模式</span>' +
        '<div class="card-name">' + esc(info.tag) + '</div>' +
        '<div class="card-desc">' + esc(info.desc) + '</div>';
      el.cards.appendChild(card);
    });
  }
  function loadRoles() {
    fetch("/api/roles").then(function (r) { return r.json(); }).then(function (data) {
      var roles = (data && data.roles) || [];
      if (!roles.length) roles = DEFAULT_ROLES.slice();
      state.roles = roles;
      renderTabs(roles);
      renderCards(roles);
      var exists = roles.some(function (r) { return r.id === state.mode; });
      if (!exists) setMode(roles[0].id); else setMode(state.mode);
    }).catch(function () {
      state.roles = DEFAULT_ROLES.slice();
      renderTabs(state.roles);
      renderCards(state.roles);
      setMode("work");
    });
  }
  function roleById(id) {
    for (var i = 0; i < state.roles.length; i++) if (state.roles[i].id === id) return state.roles[i];
    return null;
  }

  /* ---------- 渲染 ---------- */
  function renderAll() {
    el.messages.innerHTML = "";
    (state.histories[state.mode] || []).forEach(function (msg) { appendMsgNode(msg.role, msg.content); });
    if (!(state.histories[state.mode] || []).length) el.welcome.style.display = "";
    else el.welcome.style.display = "none";
    scrollBottom();
  }
  function appendMsgNode(role, content) {
    var wrap = document.createElement("div");
    wrap.className = "msg " + role;
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "ai") bubble.innerHTML = md(content);
    else bubble.textContent = content;
    wrap.appendChild(bubble);
    el.messages.appendChild(wrap);
    return wrap;
  }
  function addTyping() {
    var wrap = document.createElement("div");
    wrap.className = "msg ai typing";
    wrap.innerHTML = '<div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
    el.messages.appendChild(wrap);
    scrollBottom();
    return wrap;
  }
  function scrollBottom() { el.main.scrollTop = el.main.scrollHeight; }

  function setMode(mode) {
    if (!roleById(mode)) return;
    state.mode = mode;
    if (!state.histories[mode]) state.histories[mode] = loadHist(mode);
    var r = roleById(mode);
    applyColor(r.color);
    var tabs = el.tabs.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle("active", tabs[i].getAttribute("data-id") === mode);
      tabs[i].setAttribute("aria-selected", String(tabs[i].getAttribute("data-id") === mode));
    }
    renderAll();
  }

  /* ---------- 流式读取 ---------- */
  function readStream(res, onChunk) {
    return new Promise(function (resolve, reject) {
      if (!res.body || !res.body.getReader) {
        // 老浏览器不支持流式读取，退化为整段 JSON
        res.json().then(function (d) {
          if (d && d.reply) { onChunk(d.reply); resolve(d.reply); }
          else reject(new Error((d && d.message) || "请求失败"));
        }).catch(reject);
        return;
      }
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var acc = "", text = "";
      var stopped = false;
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) { resolve(text); return; }
          acc += decoder.decode(r.value, { stream: true });
          var idx;
          while ((idx = acc.indexOf("\n\n")) >= 0) {
            var block = acc.slice(0, idx);
            acc = acc.slice(idx + 2);
            var lines = block.split("\n");
            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (line.indexOf("data:") !== 0) continue;
              var payload = line.slice(5).trim();
              if (!payload || payload === "[DONE]") continue;
              var obj;
              try { obj = JSON.parse(payload); } catch (e) { continue; }
              if (obj.error) { stopped = true; reject(new Error(obj.message || obj.error)); return; }
              if (obj.text) { text += obj.text; onChunk(obj.text); }
            }
          }
          if (!stopped) return pump();
        }).catch(reject);
      }
      pump();
    });
  }

  /* ---------- 直连云端模式 ---------- */
  var DIRECT_KEY = "qnz_direct";
  var DIRECT_PROMPTS_KEY = "qnz_direct_prompts";
  var DEFAULT_DIRECT = { base_url: "https://api.deepseek.com/v1/chat/completions", model: "deepseek-chat", api_key: "" };
  var PROVIDERS = {
    deepseek: { base_url: "https://api.deepseek.com/v1/chat/completions", model: "deepseek-chat" },
    zhipu: { base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions", model: "glm-4-flash" },
    volc: { base_url: "https://ark.cn-beijing.volces.com/api/v3/chat/completions", model: "doubao-pro-32k" },
    qwen: { base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", model: "qwen-turbo" },
    sensenova: { base_url: "https://token.sensenova.cn/v1/chat/completions", model: "sensenova-6.8-flash-lite" },
    minimax: { base_url: "https://api.minimaxi.com/v1/chat/completions", model: "abab6.5s-chat" },
    stepfun: { base_url: "https://api.stepfun.com/v1/chat/completions", model: "step-1-8k" },
    qianfan: { base_url: "https://qianfan.baidubce.com/v2/chat/completions", model: "ernie-4.0-turbo-8k" },
    lingyi: { base_url: "https://api.lingyiwanwu.com/v1/chat/completions", model: "yi-lightning" },
    custom: { base_url: "", model: "" }
  };
  function matchProvider(url) {
    var u = String(url || "");
    for (var id in PROVIDERS) {
      if (id !== "custom" && PROVIDERS[id].base_url && u.indexOf(PROVIDERS[id].base_url) === 0) return id;
    }
    return "custom";
  }
  var DIRECT_PROMPTS = {
    work: "你是「全能助手」的工作模式：亦师亦友的工作助手，服务对象主要是大学生和个人开发者。三副面孔：师（给专业判断、挑真问题）、友（平视对话）、秘书（把杂活落地成可执行成果）。核心原则：先弄清对方到底要什么再动手；给判断但不替用户拍板；结论要能落地成下一步动作。输出风格：去AI化（不用“一站式、智能化、赋能”等套词，句子长短交错）；重要决策默认给2-3个方案并写明代价；回答末尾给一个现在能做的小事和观察窗口；不编造数据，数字拿不准标“待核实”。擅长：国创/挑战杯BP（九章结构）、路演答辩、嵌入式/STM32/ESP32/C编程调试、文档去AI化降重、纪要周报、任务拆解、职业规划。安全边界：不编造数据文件证书；重大决定给利弊清单由用户决定；法律医疗财务只给通用信息。",
    emotion: "你是「全能助手」的情感模式：全面情感顾问。三副面孔：顾问（把心理学结论转译成人话）、倾听者（先接住情绪再讲道理，不灌鸡汤）、行动教练（把分析落地成下一步）。工作流程：先接住情绪（2-4句指出感受与触发点），再分事实（已知/推测/未知），给一句首选+理由，最后给一个现在能做的小动作和观察窗口。输出风格：去AI化；心理学结论区分较强证据/理论框架/流行说法，拿不准标“待核实”。边界：不诊断心理疾病、不贴标签；出现自伤伤人风险时引导联系专业渠道（110/120/心理援助热线）；不提供操控、PUA、煤气灯类方案；尊重边界，对方明确拒绝时协助体面退出。"
  };
  function loadDirect() {
    try {
      var d = JSON.parse(localStorage.getItem(DIRECT_KEY) || "null");
      if (!d || !d.api_key) return null;
      return {
        provider: d.provider || matchProvider(d.base_url),
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
    return facts.length ? base + "\n\n【用户档案（关键事实，本机保存，仅作参考；不要编造档案外的信息）】\n" + facts.join("；") : base;
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
          while ((idx = acc.indexOf("\n\n")) >= 0) {
            var block = acc.slice(0, idx);
            acc = acc.slice(idx + 2);
            var lines = block.split("\n");
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
  function send(text) {
    text = String(text || "").trim();
    if (!text || state.busy) return;
    var mode = state.mode;
    if (!state.histories[mode]) state.histories[mode] = loadHist(mode);
    state.histories[mode].push({ role: "user", content: text });
    saveHist(mode);
    renderAll();

    state.busy = true;
    el.send.disabled = true;
    var typing = addTyping();
    hideBanner();

    var direct = loadDirect();
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
    });
  }

  /* ---------- 语音输入（Web Speech API） ---------- */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var sr = null, srOn = false;
  function initMic() {
    if (!SR) return;
    el.mic.style.display = "";
    el.mic.addEventListener("click", toggleMic);
  }
  function toggleMic() {
    if (srOn) { stopMic(); return; }
    if (!sr) {
      sr = new SR();
      sr.lang = "zh-CN";
      sr.interimResults = true;
      sr.continuous = false;
      sr.onresult = function (e) {
        var t = "";
        for (var i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
        el.input.value = t;
        autosize();
      };
      sr.onend = function () { srOn = false; el.mic.classList.remove("on"); };
      sr.onerror = function () { srOn = false; el.mic.classList.remove("on"); };
    }
    try {
      sr.start();
      srOn = true;
      el.mic.classList.add("on");
    } catch (e) { srOn = false; }
  }
  function stopMic() {
    if (sr) { try { sr.stop(); } catch (e) {} }
    srOn = false;
    el.mic.classList.remove("on");
  }

  /* ---------- 语音朗读 ---------- */
  function speakText(text) {
    if (!("speechSynthesis" in window) || !text) return;
    try {
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.lang = "zh-CN";
      u.rate = 1.0;
      window.speechSynthesis.speak(u);
    } catch (e) {}
  }
  function speakLastReply() {
    var hist = state.histories[state.mode] || [];
    for (var i = hist.length - 1; i >= 0; i--) {
      if (hist[i].role === "assistant") { speakText(hist[i].content); return; }
    }
  }

  /* ---------- 记忆 ---------- */
  function renderMem() {
    var mem = loadMem();
    el.memList.innerHTML = "";
    if (!mem.length) {
      el.memList.innerHTML = '<div class="desc">还没有记住任何事实。添加一条试试，比如你的专业、项目名。</div>';
      return;
    }
    mem.forEach(function (item, idx) {
      var row = document.createElement("div");
      row.className = "mem-item";
      var t = document.createElement("span");
      t.className = "t";
      t.textContent = item;
      var del = document.createElement("button");
      del.type = "button";
      del.textContent = "删除";
      del.addEventListener("click", function () {
        var arr = loadMem();
        arr.splice(idx, 1);
        saveMem(arr);
        renderMem();
      });
      row.appendChild(t);
      row.appendChild(del);
      el.memList.appendChild(row);
    });
  }

  /* ---------- 提示条 ---------- */
  function showBanner(text, actText, actFn) {
    el.bannerText.textContent = text;
    if (actText && actFn) {
      el.bannerAct.textContent = actText;
      el.bannerAct.onclick = actFn;
      el.bannerAct.style.display = "";
    } else {
      el.bannerAct.style.display = "none";
    }
    el.banner.classList.add("show");
  }
  function hideBanner() { el.banner.classList.remove("show"); }

  function autosize() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 120) + "px";
  }

  /* ---------- 设置 ---------- */
  function openSettings() {
    el.overlay.classList.add("show");
    renderMem();
    el.swSpeak.classList.toggle("on", loadSpeak());
    el.swSpeak.setAttribute("aria-checked", String(loadSpeak()));
    var dc = loadDirect();
    el.dcKey.value = dc ? dc.api_key : "";
    el.dcUrl.value = dc ? dc.base_url : "";
    el.dcModel.value = dc ? dc.model : "";
    el.dcProvider.value = dc ? (dc.provider || matchProvider(dc.base_url)) : "deepseek";
    var dp = loadDirectPrompts();
    el.dcPrompts.value = dp ? JSON.stringify(dp, null, 1) : "";
    el.dcStatus.textContent = dc ? "直连已启用：" + (dc.base_url || "") : "";
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (s) {
      el.stReady.textContent = s.ready ? "已就绪" : "未配置 API Key";
      el.stReady.className = "v " + (s.ready ? "ok" : "bad");
      el.stProvider.textContent = s.provider || "—";
      el.stModel.textContent = s.model || "—";
      el.stProviders.textContent = (s.providers && s.providers.length) ? s.providers.join(" / ") : "—";
      var rt = s.routing || {};
      el.stRouting.textContent = Object.keys(rt).length ? Object.keys(rt).map(function (k) { return k + "→" + rt[k]; }).join("，") : "默认";
      el.stConfig.textContent = s.config_file || "—";
    }).catch(function () {
      el.stReady.textContent = "无法连接后端";
      el.stReady.className = "v bad";
      el.stProvider.textContent = "—";
      el.stModel.textContent = "—";
      el.stProviders.textContent = "—";
      el.stRouting.textContent = "—";
      el.stConfig.textContent = "—";
    });
  }

  /* ---------- 事件绑定 ---------- */
  el.send.addEventListener("click", function () {
    send(el.input.value);
    el.input.value = "";
    autosize();
  });
  el.input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(el.input.value);
      el.input.value = "";
      autosize();
    }
  });
  el.input.addEventListener("input", autosize);
  el.speakBtn.addEventListener("click", speakLastReply);
  document.getElementById("btnSettings").addEventListener("click", openSettings);
  el.dcSave.addEventListener("click", function () {
    var key = el.dcKey.value.trim();
    if (!key) { el.dcStatus.textContent = "请先填 API Key。"; return; }
    var prov = el.dcProvider.value;
    var pre = PROVIDERS[prov] || PROVIDERS.custom;
    if (prov === "custom" && !el.dcUrl.value.trim()) {
      el.dcStatus.textContent = "自定义模式请先填接口地址。";
      return;
    }
    saveDirect({
      provider: prov,
      api_key: key,
      base_url: el.dcUrl.value.trim() || pre.base_url,
      model: el.dcModel.value.trim() || pre.model
    });
    var pv = el.dcPrompts.value.trim();
    if (pv) {
      try { saveDirectPrompts(JSON.parse(pv)); el.dcStatus.textContent = "直连已保存（含自定义人格）。"; }
      catch (e) { el.dcStatus.textContent = "人格 JSON 格式不对，已忽略人格，其余已保存。"; }
    } else {
      try { localStorage.removeItem(DIRECT_PROMPTS_KEY); } catch (e) {}
      el.dcStatus.textContent = "直连已保存（使用内置人格）。";
    }
  });
  el.dcClear.addEventListener("click", function () {
    clearDirect();
    el.dcKey.value = ""; el.dcUrl.value = ""; el.dcModel.value = ""; el.dcPrompts.value = "";
    el.dcProvider.value = "deepseek";
    el.dcStatus.textContent = "直连已关闭，将使用局域网后端。";
  });
  el.dcProvider.addEventListener("change", function () {
    var p = el.dcProvider.value;
    if (p === "custom") { el.dcUrl.value = ""; el.dcModel.value = ""; return; }
    var pre = PROVIDERS[p] || PROVIDERS.deepseek;
    el.dcUrl.value = pre.base_url;
    el.dcModel.value = pre.model;
  });
  el.overlay.addEventListener("click", function (e) { if (e.target === el.overlay) el.overlay.classList.remove("show"); });
  el.swSpeak.addEventListener("click", function () {
    var on = !loadSpeak();
    saveSpeak(on);
    el.swSpeak.classList.toggle("on", on);
    el.swSpeak.setAttribute("aria-checked", String(on));
  });
  el.memAdd.addEventListener("click", addMem);
  el.memInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); addMem(); }
  });
  function addMem() {
    var v = el.memInput.value.trim();
    if (!v) return;
    var arr = loadMem();
    if (arr.indexOf(v) < 0) arr.push(v);
    saveMem(arr);
    el.memInput.value = "";
    renderMem();
  }
  document.getElementById("btnClear").addEventListener("click", function () {
    state.histories[state.mode] = [];
    saveHist(state.mode);
    renderAll();
    el.overlay.classList.remove("show");
  });
  document.getElementById("chips").addEventListener("click", function (e) {
    var chip = e.target.closest(".chip");
    if (!chip) return;
    send(chip.textContent);
  });

  /* ---------- 启动 ---------- */
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(function () { /* 不支持则静默 */ });
  }
  initMic();
  loadRoles();
  el.input.focus();
})();
