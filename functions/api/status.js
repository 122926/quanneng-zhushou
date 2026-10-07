// 全能助手 · EdgeOne Pages 边缘函数 —— GET /api/status

function cleanKey(raw) {
  const key = String(raw || "").trim();
  if (!key || key.includes("粘贴") || key.startsWith("在这里")) return "";
  return key;
}

export function onRequestGet(context) {
  const env = context.env || {};
  return new Response(
    JSON.stringify({
      ready: !!cleanKey(env.API_KEY),
      provider: "deepseek",
      model: env.API_MODEL || "deepseek-chat",
      config_source: "EdgeOne Pages 环境变量",
    }),
    {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    }
  );
}
