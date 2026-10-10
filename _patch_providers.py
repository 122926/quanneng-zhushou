# -*- coding: utf-8 -*-
"""给全能助手.html 加直连服务商下拉（DeepSeek/智谱/豆包/通义/自定义）"""
import io

P = r'E:\git-library\quanneng-zhushou-web\全能助手.html'
s = io.open(P, encoding='utf-8').read()

def rep(old, new, tag):
    assert old in s, "anchor missing: " + tag
    s2 = s.replace(old, new, 1)
    assert s2 != s, "no change: " + tag
    return s2

# ---------- Patch 1: 直连区 UI 加服务商下拉 ----------
s = rep(
'''        <input id="dcKey" type="password" placeholder="API Key（如 sk-...）" maxlength="200" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;background:var(--bg);">''',
'''        <select id="dcProvider" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;background:var(--bg);color:var(--ink);">
          <option value="deepseek">DeepSeek</option>
          <option value="zhipu">智谱 GLM（glm-4-flash 免费）</option>
          <option value="volc">豆包（火山方舟）</option>
          <option value="qwen">通义（阿里百炼，备用）</option>
          <option value="custom">自定义（中转站等）</option>
        </select>
        <input id="dcKey" type="password" placeholder="API Key（如 sk-...）" maxlength="200" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;background:var(--bg);">''',
"provider-select-ui"
)

# ---------- Patch 2: el 定义加 dcProvider ----------
s = rep(
'''    dcKey: document.getElementById("dcKey"),''',
'''    dcKey: document.getElementById("dcKey"),
    dcProvider: document.getElementById("dcProvider"),''',
"el-dcprovider"
)

# ---------- Patch 3: PROVIDERS 预设 + matchProvider ----------
s = rep(
'''  var DEFAULT_DIRECT = { base_url: "https://api.deepseek.com/v1/chat/completions", model: "deepseek-chat", api_key: "" };''',
'''  var DEFAULT_DIRECT = { base_url: "https://api.deepseek.com/v1/chat/completions", model: "deepseek-chat", api_key: "" };
  var PROVIDERS = {
    deepseek: { base_url: "https://api.deepseek.com/v1/chat/completions", model: "deepseek-chat" },
    zhipu: { base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions", model: "glm-4-flash" },
    volc: { base_url: "https://ark.cn-beijing.volces.com/api/v3/chat/completions", model: "doubao-pro-32k" },
    qwen: { base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", model: "qwen-turbo" },
    custom: { base_url: "", model: "" }
  };
  function matchProvider(url) {
    var u = String(url || "");
    for (var id in PROVIDERS) {
      if (id !== "custom" && PROVIDERS[id].base_url && u.indexOf(PROVIDERS[id].base_url) === 0) return id;
    }
    return "custom";
  }''',
"providers-preset"
)

# ---------- Patch 4: loadDirect 返回 provider ----------
s = rep(
'''      return {
        base_url: (d.base_url || DEFAULT_DIRECT.base_url),
        model: (d.model || DEFAULT_DIRECT.model),
        api_key: d.api_key
      };''',
'''      return {
        provider: d.provider || matchProvider(d.base_url),
        base_url: (d.base_url || DEFAULT_DIRECT.base_url),
        model: (d.model || DEFAULT_DIRECT.model),
        api_key: d.api_key
      };''',
"loaddirect-provider"
)

# ---------- Patch 5: openSettings 填充下拉 ----------
s = rep(
'''    var dc = loadDirect();
    el.dcKey.value = dc ? dc.api_key : "";
    el.dcUrl.value = dc ? dc.base_url : "";
    el.dcModel.value = dc ? dc.model : "";''',
'''    var dc = loadDirect();
    el.dcKey.value = dc ? dc.api_key : "";
    el.dcUrl.value = dc ? dc.base_url : "";
    el.dcModel.value = dc ? dc.model : "";
    el.dcProvider.value = dc ? (dc.provider || matchProvider(dc.base_url)) : "deepseek";''',
"opensettings-provider"
)

# ---------- Patch 6: dcSave 保存 provider ----------
s = rep(
'''    saveDirect({
      api_key: key,
      base_url: el.dcUrl.value.trim() || DEFAULT_DIRECT.base_url,
      model: el.dcModel.value.trim() || DEFAULT_DIRECT.model
    });''',
'''    var prov = el.dcProvider.value;
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
    });''',
"dcsave-provider"
)

# ---------- Patch 7: dcClear 复位下拉 ----------
s = rep(
'''    el.dcKey.value = ""; el.dcUrl.value = ""; el.dcModel.value = ""; el.dcPrompts.value = "";
    el.dcStatus.textContent = "直连已关闭，将使用局域网后端。";''',
'''    el.dcKey.value = ""; el.dcUrl.value = ""; el.dcModel.value = ""; el.dcPrompts.value = "";
    el.dcProvider.value = "deepseek";
    el.dcStatus.textContent = "直连已关闭，将使用局域网后端。";''',
"dcclear-provider"
)

# ---------- Patch 8: dcProvider change 自动填默认 ----------
s = rep(
'''  el.dcClear.addEventListener("click", function () {
    clearDirect();
    el.dcKey.value = ""; el.dcUrl.value = ""; el.dcModel.value = ""; el.dcPrompts.value = "";
    el.dcProvider.value = "deepseek";
    el.dcStatus.textContent = "直连已关闭，将使用局域网后端。";
  });''',
'''  el.dcClear.addEventListener("click", function () {
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
  });''',
"dcprovider-change"
)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print("patched OK, new size:", len(s))
