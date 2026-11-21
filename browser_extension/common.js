// Shared helpers for the background service worker and the popup.
const MDM_DEFAULTS = {
  enabled: true,        // capture browser downloads
  port: 17890,          // must match Options → Local port in the desktop app
  minSizeKB: 0,         // skip files smaller than this (0 = no limit)
  captureAll: false,    // capture every download, not only the listed file types
  sendCookies: true,    // pass the site's cookies so logged-in downloads work
  showVideoButton: true, // floating "Download video" button over videos
  showImageButton: true, // same button over images
  autoLaunch: true,
  buttonSize: 100,      // size of the video/image button in %     // start the desktop app through chivetkh:// when it is not running
  exts: "zip rar 7z tar gz iso exe msi apk xapk dmg deb mp4 mkv avi mov webm flv m4v ts mp3 m4a flac wav aac pdf epub doc docx xls xlsx ppt pptx bin img"
};

async function mdmSettings() {
  const stored = await chrome.storage.local.get(Object.keys(MDM_DEFAULTS));
  return { ...MDM_DEFAULTS, ...stored };
}

function mdmBase(port) {
  return `http://127.0.0.1:${port}`;
}

async function mdmPing(port, timeoutMs = 900) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(`${mdmBase(port)}/ping`, {
      headers: { "X-MDM-Client": "extension" },
      signal: ctrl.signal,
      cache: "no-store"
    });
    if (!r.ok) return null;
    const j = await r.json();
    return j && ["ChivetKhDownload", "ChivetIDM", "MisterDM"].includes(j.app) ? j : null;
  } catch (e) {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// Make sure the desktop app is running. If not, start it with the chivetkh:// link it registers
// on Windows, then wait until it answers. tabId: a tab to open the link from (keeps the page).
async function mdmEnsureApp(tabId, waitMs = 25000) {
  const s = await mdmSettings();
  if (await mdmPing(s.port)) return true;
  if (!s.autoLaunch) return false;
  const link = "chivetkh://start";
  let tempTab = null;
  try {
    if (tabId == null) {
      const [t] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (t && /^https?:/i.test(t.url || "")) tabId = t.id;
    }
    if (tabId != null) await chrome.tabs.update(tabId, { url: link });
    else tempTab = await chrome.tabs.create({ url: link, active: true });
  } catch (e) {}
  const end = Date.now() + waitMs;
  let ok = false;
  while (Date.now() < end) {
    await new Promise(r => setTimeout(r, 600));
    if (await mdmPing(s.port, 700)) { ok = true; break; }
  }
  if (tempTab) { try { await chrome.tabs.remove(tempTab.id); } catch (e) {} }
  if (ok) await new Promise(r => setTimeout(r, 400));   // let the app finish opening
  return ok;
}

async function mdmStatus() {
  const s = await mdmSettings();
  try {
    const r = await fetch(`${mdmBase(s.port)}/status`, { headers: { "X-MDM-Client": "extension" }, cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch (e) {
    return null;
  }
}

async function mdmPost(path, body) {
  const s = await mdmSettings();
  try {
    const r = await fetch(`${mdmBase(s.port)}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-MDM-Client": "extension" },
      body: JSON.stringify(body || {})
    });
    return r.ok ? await r.json() : null;
  } catch (e) {
    return null;
  }
}

function mdmNewer(a, b) {   // is version a newer than b?
  const pa = String(a || "").split(/\D+/).filter(Boolean).map(Number), pb = String(b || "").split(/\D+/).filter(Boolean).map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0);
  }
  return false;
}

async function mdmCookieHeader(url) {
  try {
    const list = await chrome.cookies.getAll({ url });
    return list.map(c => `${c.name}=${c.value}`).join("; ");
  } catch (e) {
    return "";
  }
}

// payload: {url, filename?, referrer?, mime?, size?, mode?: "auto"|"http"|"ytdlp", source?}
async function mdmSend(payload) {
  const s = await mdmSettings();
  const body = { ...payload };
  if (s.sendCookies && !body.cookies && /^https?:/i.test(body.url)) {
    body.cookies = await mdmCookieHeader(body.url);
  }
  body.userAgent = navigator.userAgent;
  try {
    const r = await fetch(`${mdmBase(s.port)}/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-MDM-Client": "extension" },
      body: JSON.stringify(body)
    });
    return r.ok;
  } catch (e) {
    return false;
  }
}

function mdmGuessName(url, fallback) {
  if (fallback) {
    const parts = fallback.split(/[\\/]/);
    if (parts[parts.length - 1]) return parts[parts.length - 1];
  }
  try {
    const p = new URL(url).pathname;
    const last = decodeURIComponent(p.substring(p.lastIndexOf("/") + 1));
    return last || "";
  } catch (e) {
    return "";
  }
}

function mdmExt(name) {
  const m = /\.([a-z0-9]{1,8})$/i.exec(name || "");
  return m ? m[1].toLowerCase() : "";
}
