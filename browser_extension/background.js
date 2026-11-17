importScripts("common.js");

// URLs we hand back to the browser (app not running / refused) so we don't capture them twice.
const bypass = new Set();

const DOWNLOAD_MIMES = [
  "application/octet-stream", "application/zip", "application/x-zip-compressed", "application/x-rar-compressed",
  "application/vnd.rar", "application/x-7z-compressed", "application/x-msdownload", "application/x-msi",
  "application/vnd.android.package-archive", "application/x-iso9660-image", "application/pdf",
  "application/x-bittorrent", "application/gzip", "application/x-tar"
];

function shouldCapture(item, name, s) {
  const size = Math.max(item.fileSize || 0, item.totalBytes || 0);
  if (s.minSizeKB > 0 && size > 0 && size < s.minSizeKB * 1024) return false;
  if (s.captureAll) return true;
  const ext = mdmExt(name);
  const list = String(s.exts || "").toLowerCase().split(/[\s,;]+/).filter(Boolean);
  if (ext && list.includes(ext)) return true;
  const mime = (item.mime || "").toLowerCase();
  if (!ext && (mime.startsWith("video/") || mime.startsWith("audio/") || DOWNLOAD_MIMES.includes(mime))) return true;
  return false;
}

async function updateBadge() {
  const s = await mdmSettings();
  await chrome.action.setBadgeBackgroundColor({ color: s.enabled ? "#7c5cff" : "#64748b" });
  await chrome.action.setBadgeText({ text: s.enabled ? "" : "OFF" });
}

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title,
    message
  });
}

// ---------------------------------------------------------------------------
// 1) Capture downloads that start in the browser
// ---------------------------------------------------------------------------
chrome.downloads.onCreated.addListener(async (item) => {
  try {
    const url = item.finalUrl || item.url || "";
    if (!/^https?:/i.test(url)) return;             // blob:, data:, file: stay in the browser
    if (item.byExtensionId === chrome.runtime.id) return;
    if (item.state && item.state !== "in_progress") return;
    if (bypass.has(url)) { bypass.delete(url); return; }

    const s = await mdmSettings();
    if (!s.enabled) return;
    const name = mdmGuessName(url, item.filename);
    if (!shouldCapture(item, name, s)) return;
    if (!(await mdmPing(s.port))) {
      // app not running: hold the browser download, try to start the app, else let the browser continue
      if (!s.autoLaunch) return;
      try { await chrome.downloads.pause(item.id); } catch (e) {}
      const started = await mdmEnsureApp(null, 20000);
      if (!started) { try { await chrome.downloads.resume(item.id); } catch (e) {} return; }
    }

    try { await chrome.downloads.cancel(item.id); } catch (e) {}
    try { await chrome.downloads.erase({ id: item.id }); } catch (e) {}

    const ok = await mdmSend({
      url,
      filename: name,
      referrer: item.referrer || "",
      mime: item.mime || "",
      size: Math.max(item.fileSize || 0, item.totalBytes || 0),
      source: "capture"
    });
    if (!ok) {
      bypass.add(url);
      chrome.downloads.download({ url });
    }
  } catch (e) {
    console.warn("Chivet-kh Download capture failed", e);
  }
});

// ---------------------------------------------------------------------------
// 2) Right-click menus
// ---------------------------------------------------------------------------
function createMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "mdm-link", title: "Download with Chivet-kh", contexts: ["link"] });
    chrome.contextMenus.create({ id: "mdm-media", title: "Download this media with Chivet-kh", contexts: ["image", "video", "audio"] });
    chrome.contextMenus.create({ id: "mdm-page-video", title: "Grab video from this page (Chivet-kh)", contexts: ["page", "video", "frame"] });
    chrome.contextMenus.create({ id: "mdm-grab-all", title: "Download all files on this page (Chivet-kh)", contexts: ["page", "frame", "image", "link"] });
    chrome.contextMenus.create({ id: "mdm-links", title: "Download all videos on this page (Chivet-kh)", contexts: ["page", "frame", "link", "video"] });
    chrome.contextMenus.create({ id: "mdm-grab-images", title: "Download all images on this page (Chivet-kh)", contexts: ["page", "frame", "image"] });
  });
}

// Put the video button into tabs that were already open (after install / update / reload of the extension)
async function injectIntoOpenTabs() {
  let tabs = [];
  try { tabs = await chrome.tabs.query({ url: ["http://*/*", "https://*/*"] }); } catch (e) {}
  for (const t of tabs) {
    chrome.scripting.executeScript({ target: { tabId: t.id, allFrames: true }, files: ["content.js"] }).catch(() => {});
  }
}

chrome.runtime.onInstalled.addListener(() => { createMenus(); updateBadge(); injectIntoOpenTabs(); });
chrome.runtime.onStartup.addListener(() => { createMenus(); updateBadge(); });

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "mdm-links" && tab) {
    const r = await collectLinks(tab.id, 15);
    if (!r.ok) notify("Chivet-kh Download", r.reason === "none" ? "No video links found on this page." :
      r.reason === "offline" ? "Open the Chivet-kh Download app, then try again." : "Could not read this page.");
    return;
  }
  if ((info.menuItemId === "mdm-grab-all" || info.menuItemId === "mdm-grab-images") && tab) {
    const r = await grabTab(tab.id, info.menuItemId === "mdm-grab-images" ? "images" : "all");
    if (!r.ok) notify("Chivet-kh Download", r.reason === "offline" ? "Open the Chivet-kh Download app, then try again." : "Could not read this page.");
    return;
  }
  if (!(await mdmEnsureApp(tab ? tab.id : null))) {
    notify("Chivet-kh Download is not running", "Open the Chivet-kh Download app, then try again.");
    return;
  }
  let payload = null;
  if (info.menuItemId === "mdm-link" && info.linkUrl) {
    payload = { url: info.linkUrl, referrer: info.pageUrl || "", mode: "auto", source: "menu" };
  } else if (info.menuItemId === "mdm-media") {
    const src = info.srcUrl || "";
    if (/^https?:/i.test(src)) {
      payload = { url: src, referrer: info.pageUrl || "", mode: "http", source: "menu" };
    } else {
      // blob: video players (YouTube, Facebook…) — let yt-dlp read the page instead
      payload = { url: info.pageUrl || (tab && tab.url) || "", mode: "ytdlp", lookup: true, source: "menu" };
    }
  } else if (info.menuItemId === "mdm-page-video") {
    payload = { url: info.frameUrl || info.pageUrl || (tab && tab.url) || "", mode: "ytdlp", lookup: true, source: "menu" };
  }
  if (!payload || !/^https?:/i.test(payload.url)) {
    notify("Chivet-kh Download", "This link cannot be downloaded.");
    return;
  }
  const ok = await mdmSend(payload);
  if (!ok) notify("Chivet-kh Download", "The app refused the link. Check the port in the extension settings.");
});

// ---------------------------------------------------------------------------
// 3) Sniff media files / HLS / DASH streams per tab (used by the video button)
// ---------------------------------------------------------------------------
const tabStreams = new Map();
const FILE_EXT = /\.(mp4|webm|m4v|mov|mkv|flv|mp3|m4a|ogg|wav)(\?|$)/i;

// tabId -> Promise<list>; caching the promise means parallel responses share one list
function getStreams(tabId) {
  if (!tabStreams.has(tabId)) {
    const key = "streams_" + tabId;
    tabStreams.set(tabId, chrome.storage.session.get(key).then(r => r[key] || [], () => []));
  }
  return tabStreams.get(tabId);
}

async function addStream(tabId, entry) {
  const list = await getStreams(tabId);
  const base = entry.url.split("#")[0];
  const i = list.findIndex(s => s.url === base);
  if (i >= 0) list.splice(i, 1);
  list.unshift({ ...entry, url: base });
  const since = pageStart(tabId);
  for (let j = list.length - 1; j >= 0; j--) if (list[j].ts < since) list.splice(j, 1);
  list.length = Math.min(list.length, 20);
  chrome.storage.session.set({ ["streams_" + tabId]: list }).catch(() => {});
}

// Time the tab started loading its current page. Entries older than this belong to the previous page.
// (Compare timestamps instead of clearing, because the events can arrive in any order.)
const navStart = new Map();
function pageStart(tabId) {
  return navStart.has(tabId) ? navStart.get(tabId) : 0;
}

// ---------------------------------------------------------------------------
// Facebook: the playing video's id is inside the "efg" parameter of its fbcdn requests
// ---------------------------------------------------------------------------
const fbIds = new Map(); // tabId -> [{id, ts}]
function fbIdFromUrl(url) {
  try {
    const u = new URL(url);
    for (const key of ["efg", "_nc_vs"]) {
      const v = u.searchParams.get(key);
      if (!v) continue;
      let txt = "";
      try { txt = atob(v.replace(/-/g, "+").replace(/_/g, "/").replace(/\s/g, "")); } catch (e) { continue; }
      const m = /"(?:xpv_asset_id|video_id|asset_id)"\s*:\s*"?(\d{6,})/.exec(txt);
      if (m) return m[1];
    }
  } catch (e) {}
  return "";
}
chrome.webRequest.onBeforeRequest.addListener((d) => {
  if (d.tabId < 0) return;
  const id = fbIdFromUrl(d.url);
  if (!id) return;
  const list = fbIds.get(d.tabId) || [];
  list.push({ id, ts: Date.now() });
  if (list.length > 300) list.splice(0, list.length - 300);
  fbIds.set(d.tabId, list);
}, { urls: ["*://*.fbcdn.net/*", "*://*.facebook.com/*"], types: ["xmlhttprequest", "media", "other"] });

function currentFbId(tabId) {
  const list = fbIds.get(tabId) || [];
  const now = Date.now();
  const recent = list.filter(x => now - x.ts < 10000);
  const pool = recent.length ? recent : list.slice(-20);
  if (!pool.length) return "";
  // the playing video keeps requesting segments; pre-loaded next videos only request a few
  const score = {};
  for (const x of pool) score[x.id] = (score[x.id] || 0) + 1 + (x.ts - pool[0].ts) / 10000;
  return Object.entries(score).sort((a, b) => b[1] - a[1])[0][0];
}

chrome.webRequest.onResponseStarted.addListener((d) => {
  if (d.tabId < 0 || (d.statusCode && d.statusCode >= 400)) return;
  if (!/^https?:/i.test(d.url) || d.initiator && d.initiator.startsWith("chrome-extension://")) return;
  const h = {};
  for (const x of d.responseHeaders || []) h[x.name.toLowerCase()] = x.value || "";
  const ctype = (h["content-type"] || "").split(";")[0].trim().toLowerCase();
  let kind = "";
  if (/mpegurl/.test(ctype) || /\.m3u8(\?|$)/i.test(d.url)) kind = "hls";
  else if (ctype === "application/dash+xml" || /\.mpd(\?|$)/i.test(d.url)) kind = "dash";
  else if (ctype.startsWith("video/") || ctype.startsWith("audio/") || FILE_EXT.test(d.url)) kind = "file";
  if (!kind) return;
  if (ctype === "video/mp2t" || /\.(ts|m4s|aac)(\?|$)/i.test(d.url)) return;        // stream segments
  if (/[?&](range|bytestart|byteend)=/i.test(d.url)) return;                         // chunked players (YouTube/Facebook)
  let size = 0;
  const cr = /\/(\d+)\s*$/.exec(h["content-range"] || "");
  if (cr) size = +cr[1]; else if (h["content-length"]) size = +h["content-length"];
  if (kind === "file" && size && size < 150 * 1024) return;                         // tiny previews / sounds
  addStream(d.tabId, { url: d.url, kind, ctype: ctype || (kind === "file" ? "video/mp4" : ""), size, ts: d.timeStamp });
}, { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other"] }, ["responseHeaders"]);

// a new page in the tab → forget the old page's streams (fires before the page's own requests)
chrome.webRequest.onBeforeRequest.addListener((d) => {
  if (d.tabId >= 0) navStart.set(d.tabId, Math.max(pageStart(d.tabId), d.timeStamp));
}, { urls: ["<all_urls>"], types: ["main_frame"] });
chrome.tabs.onRemoved.addListener((tabId) => {
  tabStreams.delete(tabId);
  fbIds.delete(tabId);
  navStart.delete(tabId);
  chrome.storage.session.remove("streams_" + tabId).catch(() => {});
});

// ---------------------------------------------------------------------------
// 4) Grab every file on a page (links, images, video, audio, detected streams)
// ---------------------------------------------------------------------------
function mdmCollect() {
  const out = [], seen = new Set();
  const abs = u => { try { return new URL(u, location.href).href; } catch (e) { return ""; } };
  const add = (u, tag, extra) => {
    u = abs(u);
    if (!/^https?:/i.test(u) || seen.has(u)) return;
    seen.add(u);
    out.push(Object.assign({ url: u, tag }, extra || {}));
  };
  const best = ss => {
    let b = "", bw = 0;
    (ss || "").split(",").forEach(part => {
      const [u, d] = part.trim().split(/\s+/);
      const w = parseFloat(d) || 1;
      if (u && w >= bw) { bw = w; b = u; }
    });
    return b;
  };
  document.querySelectorAll("img").forEach(im => {
    const u = best(im.getAttribute("srcset")) || im.currentSrc || im.src || im.getAttribute("data-src") ||
      im.getAttribute("data-original") || im.getAttribute("data-lazy-src");
    if (u) add(u, "img", { w: im.naturalWidth || 0, h: im.naturalHeight || 0, text: (im.alt || "").slice(0, 80) });
  });
  document.querySelectorAll("picture source[srcset], source[type^='image']").forEach(s => add(best(s.getAttribute("srcset")), "img"));
  document.querySelectorAll("video, audio").forEach(m => {
    [m.currentSrc, m.src, ...Array.from(m.querySelectorAll("source")).map(s => s.src)]
      .forEach(u => { if (u && !u.startsWith("blob:")) add(u, m.tagName.toLowerCase()); });
    if (m.poster) add(m.poster, "img");
  });
  document.querySelectorAll("a[href]").forEach(a => add(a.href, "a", { text: (a.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80) }));
  document.querySelectorAll("[style*='url(']").forEach(el => {
    const m = /url\(["']?([^"')]+)["']?\)/.exec(el.getAttribute("style") || "");
    if (m) add(m[1], "img");
  });
  document.querySelectorAll("meta[property='og:image'], meta[property='og:video'], meta[name='twitter:image']")
    .forEach(m => add(m.content, /video/.test(m.getAttribute("property") || "") ? "video" : "img"));
  return { title: document.title, page: location.href, items: out.slice(0, 5000) };
}

async function grabTab(tabId, which) {
  const s = await mdmSettings();
  if (!(await mdmEnsureApp(tabId))) return { ok: false, reason: "offline" };
  let results = [];
  try {
    results = await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, func: mdmCollect });
  } catch (e) {
    return { ok: false, reason: "blocked", error: String(e && e.message || e) };
  }
  let items = [], title = "", page = "";
  for (const r of results) {
    if (!r || !r.result) continue;
    if (!page) { title = r.result.title; page = r.result.page; }
    items.push(...r.result.items);
  }
  const since = pageStart(tabId);
  for (const st of (await getStreams(tabId)).filter(x => x.ts >= since)) {
    items.push({ url: st.url, tag: st.kind === "file" ? "media" : st.kind, size: st.size || 0 });
  }
  const seen = new Set();
  items = items.filter(i => !seen.has(i.url) && seen.add(i.url));
  if (which === "images") items = items.filter(i => i.tag === "img");
  const origins = [...new Set(items.map(i => { try { return new URL(i.url).origin; } catch (e) { return ""; } }))].filter(Boolean).slice(0, 60);
  const cookies = {};
  if (s.sendCookies) for (const o of origins) { const c = await mdmCookieHeader(o + "/"); if (c) cookies[o] = c; }
  try {
    const r = await fetch(`${mdmBase(s.port)}/add-batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-MDM-Client": "extension" },
      body: JSON.stringify({ page, title, items, cookies, which, userAgent: navigator.userAgent })
    });
    return { ok: r.ok, count: items.length };
  } catch (e) {
    return { ok: false, reason: "offline" };
  }
}

// ---------------------------------------------------------------------------
// 4b) Collect every video link on a page (Facebook page Reels tab, YouTube channel, TikTok profile…)
//     Scrolls down to load more, then sends the list to the app's "Download links" window.
// ---------------------------------------------------------------------------
async function mdmCollectVideoLinks(scrolls) {
  const RX = [
    /facebook\.com\/reel\/\d{6,}/, /facebook\.com\/(?:[^/?#]+\/)?videos\/(?:[^/?#]+\/)?\d{6,}/, /facebook\.com\/watch\/?\?(?:.*&)?v=\d{6,}/,
    /fb\.watch\/\w+/, /youtube\.com\/watch\?(?:.*&)?v=[\w-]{11}/, /youtube\.com\/shorts\/[\w-]{11}/, /youtu\.be\/[\w-]{11}/,
    /tiktok\.com\/@[^/]+\/(?:video|photo)\/\d{6,}/, /instagram\.com\/(?:[^/]+\/)?(?:reels?|p|tv)\/[\w-]{5,}/,
    /(?:twitter|x)\.com\/[^/]+\/status\/\d{6,}/, /vimeo\.com\/\d{5,}/, /dailymotion\.com\/video\/\w+/
  ];
  const clean = u => {
    try {
      const x = new URL(u, location.href);
      if (/youtube\.com$/.test(x.hostname) && x.pathname === "/watch") return `https://www.youtube.com/watch?v=${x.searchParams.get("v")}`;
      if (/facebook\.com$/.test(x.hostname) && /^\/watch/.test(x.pathname)) return `https://www.facebook.com/watch/?v=${x.searchParams.get("v")}`;
      x.hash = ""; x.search = "";
      return x.href.replace(/\/$/, "");
    } catch (e) { return ""; }
  };
  const found = new Map();
  const grab = () => {
    for (const a of document.querySelectorAll("a[href]")) {
      const h = a.href;
      if (!RX.some(r => r.test(h))) continue;
      const u = clean(h);
      if (u && !found.has(u)) found.set(u, (a.getAttribute("aria-label") || a.textContent || "").trim().replace(/\s+/g, " ").slice(0, 120));
    }
  };
  grab();
  let still = 0;
  for (let i = 0; i < scrolls && still < 4; i++) {
    const before = found.size, h = document.documentElement.scrollHeight;
    window.scrollTo(0, h);
    await new Promise(r => setTimeout(r, 1200));
    grab();
    still = (found.size === before && document.documentElement.scrollHeight === h) ? still + 1 : 0;
  }
  return { page: location.href, title: document.title, links: [...found.entries()].map(([url, text]) => ({ url, text })) };
}

async function collectLinks(tabId, scrolls) {
  if (!(await mdmEnsureApp(tabId))) return { ok: false, reason: "offline" };
  let res;
  try {
    [res] = await chrome.scripting.executeScript({ target: { tabId }, func: mdmCollectVideoLinks, args: [scrolls] });
  } catch (e) {
    return { ok: false, reason: "blocked" };
  }
  const data = (res && res.result) || { links: [] };
  if (!data.links.length) return { ok: false, reason: "none" };
  const s = await mdmSettings();
  const origins = [...new Set(data.links.map(l => { try { return new URL(l.url).origin; } catch (e) { return ""; } }))].filter(Boolean);
  const cookies = {};
  if (s.sendCookies) for (const o of origins.slice(0, 10)) { const c = await mdmCookieHeader(o + "/"); if (c) cookies[o] = c; }
  try {
    const r = await fetch(`${mdmBase(s.port)}/add-links`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-MDM-Client": "extension" },
      body: JSON.stringify({ ...data, cookies, userAgent: navigator.userAgent })
    });
    return { ok: r.ok, count: data.links.length };
  } catch (e) {
    return { ok: false, reason: "offline" };
  }
}

// ---------------------------------------------------------------------------
// 5) Messages from the popup and the video button
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    const s = await mdmSettings();
    if (msg && msg.type === "send") {
      if (!(await mdmEnsureApp(sender.tab ? sender.tab.id : null))) return reply({ ok: false, reason: "offline" });
      const payload = { url: msg.url, mode: msg.mode || "auto", source: msg.source || (sender.tab ? "video-button" : "popup") };
      for (const k of ["referrer", "quality", "filename", "title"]) if (msg[k]) payload[k] = String(msg[k]);
      if (msg.lookup) payload.lookup = true;
      if (msg.quick) payload.quick = true;
      if (msg.kind) payload.kind = String(msg.kind);
      reply({ ok: await mdmSend(payload) });
    } else if (msg && msg.type === "ping") {
      reply({ ok: !!(await mdmPing(s.port)) });
    } else if (msg && msg.type === "streams") {
      const tabId = sender.tab ? sender.tab.id : -1;
      const since = pageStart(tabId);
      reply({ streams: tabId >= 0 ? (await getStreams(tabId)).filter(x => x.ts >= since) : [] });
    } else if (msg && msg.type === "links") {
      const tabId = msg.tabId || (sender.tab && sender.tab.id);
      reply(tabId ? await collectLinks(tabId, msg.scrolls == null ? 15 : msg.scrolls) : { ok: false });
    } else if (msg && msg.type === "fbid") {
      reply({ id: sender.tab ? currentFbId(sender.tab.id) : "" });
    } else if (msg && msg.type === "grab") {
      const tabId = msg.tabId || (sender.tab && sender.tab.id);
      reply(tabId ? await grabTab(tabId, msg.which || "all") : { ok: false });
    } else if (msg && msg.type === "inject" && msg.tabId) {
      try {
        await chrome.scripting.executeScript({ target: { tabId: msg.tabId, allFrames: true }, files: ["content.js"] });
        reply({ ok: true });
      } catch (e) {
        reply({ ok: false, error: String(e && e.message || e) });
      }
    } else if (msg && msg.type === "badge") {
      await updateBadge();
      reply({ ok: true });
    } else {
      reply({ ok: false });
    }
  })();
  return true; // keep the channel open for the async reply
});
