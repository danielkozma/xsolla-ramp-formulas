/**
 * Password gate for the whole site.
 *
 * The password lives in the SITE_PASSWORD environment variable on Vercel —
 * nothing secret is committed here.
 *
 * The password itself never travels over the network. The login page hashes
 * what you type in the browser and stores the hash in a cookie; this middleware
 * hashes SITE_PASSWORD and compares the two. Changing SITE_PASSWORD therefore
 * signs everyone out on its own.
 *
 * This is a shared-link gate, not per-user auth: anyone with the password gets in.
 */

export const config = {
  // Everything except Vercel's own internals. Static assets are gated too, so
  // nothing under /data or /fonts is readable without the password.
  matcher: ['/((?!_vercel/).*)'],
  runtime: 'edge',
};

const COOKIE = 'xcf_gate';
const SALT = 'xsolla-ramp-formulas:v1:'; // keeps the hash off generic rainbow tables
const MAX_AGE = 60 * 60 * 24 * 30; // 30 days

async function tokenFor(password) {
  const bytes = new TextEncoder().encode(SALT + password);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Constant-time-ish comparison, so a wrong guess leaks no timing signal. */
function sameToken(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function readCookie(request, name) {
  const header = request.headers.get('cookie') || '';
  for (const part of header.split(';')) {
    const eq = part.indexOf('=');
    if (eq === -1) continue;
    if (part.slice(0, eq).trim() === name) return part.slice(eq + 1).trim();
  }
  return null;
}

export default async function middleware(request) {
  const password = process.env.SITE_PASSWORD;

  if (!password) {
    return loginPage(503, 'SITE_PASSWORD is not set on this deployment.');
  }

  const expected = await tokenFor(password);
  if (sameToken(readCookie(request, COOKIE) || '', expected)) {
    return; // authenticated — let the request fall through to the static file
  }

  return loginPage(401, null);
}

function loginPage(status, notice) {
  const html = `<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Xsolla Colour Formulas</title>
<style>
  :root{--ink:#16181C;--ink-2:#494F59;--ink-3:#767D8A;--bg:#F2F2F0;--panel:#FFF;
        --rule:#E3E3DF;--rule-2:#CFCFC9;--accent:#16181C;--bad:#B4231E}
  @media (prefers-color-scheme:dark){
    :root{--ink:#F2F2F0;--ink-2:#B7BCC4;--ink-3:#8A909B;--bg:#121316;--panel:#1B1D21;
          --rule:#2A2D33;--rule-2:#3A3E45;--accent:#F2F2F0;--bad:#F08078}
  }
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;
       background:var(--bg);color:var(--ink);
       font:400 14px/20px ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  form{width:100%;max-width:340px;background:var(--panel);border:1px solid var(--rule);
       border-radius:14px;padding:28px}
  h1{margin:0 0 6px;font-size:19px;line-height:24px;font-weight:500}
  p{margin:0 0 20px;color:var(--ink-3);font-size:13px;line-height:18px}
  p.msg{margin:0 0 14px;color:var(--bad)}
  p.msg[hidden]{display:none}
  label{display:block;margin:0 0 6px;font-size:12px;color:var(--ink-2)}
  input{width:100%;height:38px;padding:0 11px;border:1px solid var(--rule-2);border-radius:8px;
        background:var(--panel);color:var(--ink);font:inherit}
  input:focus{outline:2px solid var(--ink);outline-offset:1px;border-color:transparent}
  button{width:100%;height:38px;margin-top:14px;border:0;border-radius:8px;background:var(--accent);
         color:var(--bg);font:500 14px/1 inherit;cursor:pointer}
  button:hover{opacity:.88}
</style></head>
<body>
  <form id="gate" autocomplete="on">
    <h1>Xsolla Colour Formulas</h1>
    <p>This page is private. Enter the password to continue.</p>
    <p class="msg" id="msg"${notice ? '' : ' hidden'}>${notice || ''}</p>
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
    <button type="submit">Enter</button>
    <noscript><p class="msg" style="margin-top:14px" >This page needs JavaScript to sign in.</p></noscript>
  </form>
<script>
  const SALT = ${JSON.stringify(SALT)}, COOKIE = ${JSON.stringify(COOKIE)}, MAX_AGE = ${MAX_AGE};
  const msg = document.getElementById('msg');

  /* Coming back to this page after a submit means the hash did not match. */
  if (sessionStorage.getItem('xcf-tried')) {
    sessionStorage.removeItem('xcf-tried');
    msg.textContent = 'That password is not right.';
    msg.hidden = false;
  }

  document.getElementById('gate').addEventListener('submit', async (e) => {
    e.preventDefault();
    const value = document.getElementById('password').value;
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(SALT + value));
    const token = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
    const secure = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = COOKIE + '=' + token + '; Path=/; Max-Age=' + MAX_AGE + '; SameSite=Lax' + secure;
    sessionStorage.setItem('xcf-tried', '1');
    location.reload();
  });
</script>
</body></html>`;

  return new Response(html, {
    status,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' },
  });
}
