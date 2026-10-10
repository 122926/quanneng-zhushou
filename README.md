# 全能助手 · 手机网页版

把豆包里的「全能助手」技能搬出豆包体系，做成一个**手机浏览器直接能用**的聊天应用。
工作问题走工作知识，情感问题走情感知识，和豆包技能里的人格一致。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `server.py` | 后端，仅用 Python 标准库，**零依赖、不用装任何包** |
| `全能助手.html` | 前端聊天界面，手机/电脑浏览器自适应 |
| `config.example.json` | 配置模板（复制改名成 `config.json` 后填写） |
| `config.json` | 实际配置（你自己建，含 API Key） |
| `prompts.json` | **人格单一来源**（work/emotion 两段提示词），改人格只改它 |
| `sync_prompts.py` | 同步脚本：把 `prompts.json` 同步到 EdgeOne 端 `functions/api/prompts.js` |

## v2 新增能力（2026-10-09）

1. **流式输出**：回复逐字流出（SSE），前端打字机效果，默认开启，无需配置。
2. **语音输入**：手机/电脑浏览器自带 Web Speech API，输入框左侧麦克风按钮，支持中文语音转文字（浏览器不支持时自动隐藏）。
3. **语音朗读**：顶栏喇叭按钮朗读最后一条回复；设置里可开启"回复完成后自动朗读"（本地语音合成，免费）。
4. **多服务商（Provider 可插拔）**：`config.json` 的 `providers` 里可配多个服务商（DeepSeek/火山方舟/任何 OpenAI 兼容接口），`mode_routing` 可指定每个模式用哪个服务商。不填 `providers` 时保持旧版单服务商写法，完全兼容。
5. **轻量记忆**：设置面板里可添加"记住的关键事实"，每次对话自动带上（仅存本浏览器 localStorage）。
6. **角色库**：`prompts.json` 的 `roles` 数组可加任意角色（id/name/color/prompt），前端顶栏自动生成切换标签，各角色历史独立保存。

## 第一次使用（5 分钟）

1. **复制配置**：把 `config.example.json` 复制一份，改名 `config.json`，用记事本打开。
2. **填 API Key**（二选一）：
   - **DeepSeek**（推荐，便宜）：到 https://platform.deepseek.com 注册 → 充值少量（比如 10 元）→ API Keys 页面创建 Key → 粘贴进 `config.json` 的 `api_key`。
   - **豆包/火山方舟**：到火山方舟控制台创建推理接入点，`base_url` 填 `https://ark.cn-beijing.volces.com/api/v3/chat/completions`，`model` 填接入点 ID，`provider` 填 `volcengine`。
3. **启动**：双击运行，或在命令行执行 `python server.py`。
4. **打开**：
   - 电脑上：浏览器访问 `http://127.0.0.1:8787`
   - 手机上：确保手机和电脑连**同一个 Wi-Fi**，浏览器访问 `http://<电脑局域网IP>:8787`（如何查 IP：命令行执行 `ipconfig`，看"IPv4 地址"那行）。

## 怎么找手机能用的 IP

按 `Win+R` → 输入 `cmd` → 回车 → 输入 `ipconfig` → 找到你正在用的网络（Wi-Fi 或以太网）下的 **IPv4 地址**，例如 `192.168.1.10`。手机浏览器输入 `http://192.168.1.10:8787` 即可。

> 如果手机打不开：先确认手机和电脑在同一 Wi-Fi；再检查 Windows 防火墙是否拦截了 Python（弹出防火墙提示时选"允许访问"）。

## 费用参考（DeepSeek，2026 年官方计价）

- 价格按 token 计，日常问答量级非常便宜。以官方页面实时价格为准，这里给量级感受：
  - 大约 100 万 token（几十万字级别的输入）在个位数到十几元人民币的量级；
  - 纯聊天问答，10 元余额能用非常久（几十万到上百万字）。
- 省钱技巧：`max_history` 改成 10 可以少带历史、少花输入费；日常问题不需要调高。

## 以后改人格（只用改一处）

1. 编辑 `prompts.json` 里的 `work` / `emotion` 两段文字，保存。
2. 按你用的端生效：
   - **本地版**：重启 `server.py` 即可。
   - **腾讯云函数版**：运行 `python cloud\build_scf.py` 重新生成 `cloud/scf_handler.py`，把新文件粘贴到云函数控制台并部署（见 `cloud/部署说明.md`）。
   - **EdgeOne 版**：运行 `python sync_prompts.py` 更新 `edgeone/functions/api/prompts.js`，然后 git add / commit / push（见 `edgeone/部署说明.md`）。

> `server.py`、`cloud/scf_handler.py`、`edgeone/functions/api/chat.js` 里不再直接改人格；它们内置的提示词只是 `prompts.json` 缺失时的兜底。

## 常见问题

- **打开页面提示"缺少 config.json"**：你还没复制配置文件，按上面第一步做。
- **提示"api_key 为空"**：`config.json` 里 `api_key` 还是占位文字，改成真实 Key。
- **提示 API 报错（API_HTTP_401）**：Key 填错或没生效，回平台检查。
- **端口被占用**：命令行用 `PORT=9000 python server.py` 换端口，访问时把 8787 换成 9000。
- **聊天记录**：保存在浏览器本地（localStorage），清浏览器数据会清空。

## 安全提醒

- API Key 只存在你电脑的 `config.json` 里，不发给前端，不公开；但**不要把 config.json 发给别人**。
- 根目录 `.gitignore` 已忽略 `config.json`：即使以后 `git init` 提交，Key 也不会进仓库历史（`config.example.json` 是模板，正常入库）。
- 本应用只在你自己的电脑上运行，不经过第三方服务器中转（除了你调用的大模型 API 本身）。
- 涉及重大决定（合同、就医、大额花销、法律）请以专业机构为准，本应用只提供辅助分析。
