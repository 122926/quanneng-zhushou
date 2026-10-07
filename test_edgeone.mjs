// 本地验证 EdgeOne Pages 边缘函数（node .mjs 直接跑，无第三方依赖）
import { onRequestGet } from "./functions/api/status.js";
import { onRequestPost } from "./functions/api/chat.js";

let pass = 0;
function ok(name) { pass++; console.log("PASS " + name); }
function fail(name, extra) { console.error("FAIL " + name + (extra ? " -> " + JSON.stringify(extra) : "")); process.exitCode = 1; }

function ctx(env, body) {
  return {
    env,
    request: new Request("http://x/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body == null ? undefined : (typeof body === "string" ? body : JSON.stringify(body)),
    }),
  };
}
async function readJson(resp) { return JSON.parse(await resp.text()); }

// ---- status.js ----
(async () => {
  const r1 = await onRequestGet({ env: {} });
  const d1 = await readJson(r1);
  if (r1.status === 200 && d1.ready === false && d1.config_source.includes("EdgeOne")) ok("status: 无 Key -> ready=false");
  else fail("status: 无 Key", { status: r1.status, d1 });

  const r2 = await onRequestGet({ env: { API_KEY: "sk-real-123" } });
  const d2 = await readJson(r2);
  if (d2.ready === true) ok("status: 有 Key -> ready=true");
  else fail("status: 有 Key", d2);

  // ---- chat.js 无 Key 分支 ----
  let r = await onRequestPost(ctx({}, { mode: "work", messages: [{ role: "user", content: "你好" }] }));
  let d = await readJson(r);
  if (r.status === 503 && d.error === "NO_API_KEY") ok("chat: 无 Key -> 503 NO_API_KEY");
  else fail("chat: 无 Key", { status: r.status, d });

  r = await onRequestPost(ctx({ API_KEY: "在这里粘贴你的API Key" }, { mode: "work", messages: [] }));
  d = await readJson(r);
  if (r.status === 503 && d.error === "NO_API_KEY") ok("chat: 占位 Key 视为未设置");
  else fail("chat: 占位 Key", { status: r.status, d });

  // ---- chat.js 请求校验 ----
  r = await onRequestPost(ctx({ API_KEY: "sk-x" }, "not-json{{"));
  d = await readJson(r);
  if (r.status === 400 && d.error === "BAD_REQUEST") ok("chat: 非法 JSON -> 400");
  else fail("chat: 非法 JSON", { status: r.status, d });

  r = await onRequestPost(ctx({ API_KEY: "sk-x" }, { mode: "zzz", messages: "oops" }));
  d = await readJson(r);
  if (r.status === 400 && d.error === "BAD_REQUEST") ok("chat: messages 非数组 -> 400");
  else fail("chat: messages 非数组", { status: r.status, d });

  // ---- chat.js 成功/失败分支（mock fetch）----
  const realFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url, opts) => {
      ok("chat: 请求发往 DeepSeek（URL=" + url + ", 带 Bearer）");
      const auth = opts.headers.Authorization || opts.headers.authorization || "";
      if (!auth.includes("Bearer sk-fake")) fail("chat: 缺少 Bearer", { auth });
      return new Response(JSON.stringify({ choices: [{ message: { content: "模拟回复" } }] }), { status: 200 });
    };
    r = await onRequestPost(ctx({ API_KEY: "sk-fake", API_MODEL: "deepseek-chat" }, { mode: "emotion", messages: [{ role: "user", content: "我很难过" }] }));
    d = await readJson(r);
    if (r.status === 200 && d.reply === "模拟回复") ok("chat: 成功返回 reply");
    else fail("chat: 成功分支", { status: r.status, d });
  } finally {
    globalThis.fetch = realFetch;
  }

  try {
    globalThis.fetch = async () => { throw new Error("net down"); };
    r = await onRequestPost(ctx({ API_KEY: "sk-fake" }, { mode: "work", messages: [{ role: "user", content: "hi" }] }));
    d = await readJson(r);
    if (r.status === 502 && d.error === "API_NETWORK") ok("chat: 网络失败 -> 502 API_NETWORK");
    else fail("chat: 网络失败", { status: r.status, d });
  } finally {
    globalThis.fetch = realFetch;
  }

  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ error: "invalid key" }), { status: 401 });
    r = await onRequestPost(ctx({ API_KEY: "sk-bad" }, { mode: "work", messages: [{ role: "user", content: "hi" }] }));
    d = await readJson(r);
    if (r.status === 502 && String(d.error).startsWith("API_HTTP_")) ok("chat: 上游 401 -> API_HTTP_401");
    else fail("chat: 上游 401", { status: r.status, d });
  } finally {
    globalThis.fetch = realFetch;
  }

  console.log(pass + " tests passed");
})();
