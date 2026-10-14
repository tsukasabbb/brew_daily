/**
 * BREW DAILY — メルマガ登録 Worker
 *
 * エンドポイント:
 *   POST /subscribe            メール登録（公開）
 *   POST /unsubscribe          メール解除（公開）
 *   GET  /admin/subscribers    登録者一覧（管理者専用）
 *   GET  /admin/export         メール一覧をテキスト出力（brew_magazine.py 用）
 *   DELETE /admin/subscriber   1件削除（管理者専用）
 */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

export default {
  async fetch(request, env) {
    // プリフライトリクエスト
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    // ── 公開エンドポイント ──────────────────────────
    if (path === "/subscribe" && request.method === "POST") {
      return handleSubscribe(request, env);
    }

    if (path === "/unsubscribe" && request.method === "POST") {
      return handleUnsubscribe(request, env);
    }

    // ── 管理者エンドポイント ────────────────────────
    if (path.startsWith("/admin/")) {
      const auth = request.headers.get("Authorization") || "";
      const token = auth.replace("Bearer ", "").trim();
      if (token !== env.ADMIN_TOKEN) {
        return json({ error: "Unauthorized" }, 401);
      }

      if (path === "/admin/subscribers" && request.method === "GET") {
        return handleListSubscribers(env);
      }
      if (path === "/admin/export" && request.method === "GET") {
        return handleExport(env);
      }
      if (path === "/admin/subscriber" && request.method === "DELETE") {
        return handleDeleteSubscriber(request, env);
      }
    }

    return json({ error: "Not found" }, 404);
  },
};

// ── メール登録 ───────────────────────────────────────
async function handleSubscribe(request, env) {
  const body = await request.json().catch(() => ({}));
  const email = (body.email || "").trim().toLowerCase();

  if (!isValidEmail(email)) {
    return json({ error: "メールアドレスが正しくありません" }, 400);
  }

  // 既存チェック
  const existing = await env.SUBSCRIBERS.get(`sub:${email}`);
  if (existing) {
    return json({ message: "既に登録済みです" }, 200);
  }

  // KV に保存（メタ情報付き）
  await env.SUBSCRIBERS.put(
    `sub:${email}`,
    JSON.stringify({
      email,
      subscribedAt: new Date().toISOString(),
      active: true,
    })
  );

  // カウンターを更新
  const countStr = await env.SUBSCRIBERS.get("meta:count");
  const count = parseInt(countStr || "0") + 1;
  await env.SUBSCRIBERS.put("meta:count", String(count));

  return json({ message: "登録完了！毎朝最新のビール情報をお届けします🍺" }, 200);
}

// ── 登録解除 ──────────────────────────────────────────
async function handleUnsubscribe(request, env) {
  const body = await request.json().catch(() => ({}));
  const email = (body.email || "").trim().toLowerCase();

  if (!isValidEmail(email)) {
    return json({ error: "メールアドレスが正しくありません" }, 400);
  }

  const existing = await env.SUBSCRIBERS.get(`sub:${email}`);
  if (!existing) {
    return json({ message: "登録が見つかりません" }, 404);
  }

  await env.SUBSCRIBERS.delete(`sub:${email}`);

  const countStr = await env.SUBSCRIBERS.get("meta:count");
  const count = Math.max(0, parseInt(countStr || "1") - 1);
  await env.SUBSCRIBERS.put("meta:count", String(count));

  return json({ message: "配信を停止しました" }, 200);
}

// ── 登録者一覧（管理者） ─────────────────────────────
async function handleListSubscribers(env) {
  const list = await env.SUBSCRIBERS.list({ prefix: "sub:" });
  const subscribers = [];

  for (const key of list.keys) {
    const data = await env.SUBSCRIBERS.get(key.name);
    if (data) {
      subscribers.push(JSON.parse(data));
    }
  }

  subscribers.sort((a, b) =>
    new Date(b.subscribedAt) - new Date(a.subscribedAt)
  );

  return json({ count: subscribers.length, subscribers }, 200);
}

// ── エクスポート（brew_magazine.py 用） ───────────────
async function handleExport(env) {
  const list = await env.SUBSCRIBERS.list({ prefix: "sub:" });
  const emails = [];

  for (const key of list.keys) {
    const data = await env.SUBSCRIBERS.get(key.name);
    if (data) {
      const sub = JSON.parse(data);
      if (sub.active !== false) emails.push(sub.email);
    }
  }

  return new Response(emails.join(","), {
    headers: { ...CORS, "Content-Type": "text/plain" },
  });
}

// ── 1件削除（管理者） ────────────────────────────────
async function handleDeleteSubscriber(request, env) {
  const body = await request.json().catch(() => ({}));
  const email = (body.email || "").trim().toLowerCase();

  await env.SUBSCRIBERS.delete(`sub:${email}`);
  return json({ message: `${email} を削除しました` }, 200);
}

// ── ユーティリティ ────────────────────────────────────
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}
