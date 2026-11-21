// Chivet-kh Download — "Download this video" button over videos on any page.
(() => {
  // ------------------------------------------------------------------ one live instance per frame
  // After the extension is reloaded, the old copy of this script stays in open tabs but can no longer talk to
  // the extension. Every new copy tells older copies to shut down, then takes over.
  const INSTANCE = Math.random().toString(36).slice(2);
  window.dispatchEvent(new CustomEvent("chivet-kh-button-takeover", { detail: INSTANCE }));
  let alive = true;
  const cleanups = [];
  const on = (target, type, fn, opts) => { target.addEventListener(type, fn, opts); cleanups.push(() => target.removeEventListener(type, fn, opts)); };
  function shutdown() {
    if (!alive) return;
    alive = false;
    cleanups.forEach(f => { try { f(); } catch (e) {} });
    try { host.remove(); } catch (e) {}
  }
  on(window, "chivet-kh-button-takeover", e => { if (e.detail !== INSTANCE) shutdown(); });
  document.querySelectorAll("chivet-kh-button").forEach(n => n.remove());
  const extOk = () => { try { return !!(chrome.runtime && chrome.runtime.id); } catch (e) { return false; } };

  const MIN_W = 200, MIN_H = 112;

  // Video platforms: the page link goes to yt-dlp (their streams are split / encrypted).
  const SITES = [
    { host: /(^|\.)(youtube\.com|youtube-nocookie\.com|youtu\.be)$/, strong: /\/watch\?(?:.*&)?v=[\w-]{6,}|\/shorts\/[\w-]{6,}|youtu\.be\/[\w-]{6,}|\/embed\/[\w-]{6,}|\/live\/[\w-]{6,}/, weak: null },
    { host: /(^|\.)(facebook\.com|fb\.watch)$/, fb: true, strong: /\/videos\/(?:[^/?#]+\/)?\d{6,}|\/reel\/\d{6,}|\/watch\/?\?(?:.*&)?v=\d{6,}|\/share\/[vr]\/\w+|fb\.watch\/\w+/, weak: /\/posts\/[\w.-]+|permalink\.php\?|story\.php\?|\/permalink\/\d+/ },
    { host: /(^|\.)tiktok\.com$/, strong: /\/video\/\d{6,}|\/photo\/\d{6,}/, weak: null },
    { host: /(^|\.)instagram\.com$/, strong: /\/reels?\/[\w-]{5,}|\/tv\/[\w-]{5,}/, weak: /\/p\/[\w-]{5,}/ },
    { host: /(^|\.)(twitter\.com|x\.com)$/, strong: /\/status\/\d{6,}/, weak: null },
    { host: /(^|\.)vimeo\.com$/, strong: /vimeo\.com\/(video\/)?\d{5,}/, weak: null },
    { host: /(^|\.)dailymotion\.com$/, strong: /\/video\/\w+/, weak: null },
    { host: /(^|\.)reddit\.com$/, strong: /\/comments\/[a-z0-9]+/i, weak: null },
    { host: /(^|\.)bilibili\.(com|tv)$/, strong: /\/video\/\w+/, weak: null },
    { host: /(^|\.)twitch\.tv$/, strong: /\/videos\/\d+|\/clip\/[\w-]+/, weak: null },
    { host: /(^|\.)threads\.(net|com)$/, strong: /\/post\/[\w-]+/, weak: null },
    { host: /(^|\.)pinterest\.[a-z.]+$/, strong: /\/pin\/\d+/, weak: null },
  ];
  const site = SITES.find(s => s.host.test(location.hostname));
  // 红果短剧: plain MP4 files; switching episodes does not change the address, so read the playing file instead
  const HG = /(^|\.)hongguoduanju\.com$/.test(location.hostname);

  let enabled = true, imagesOn = true;
  const setScale = v => { const k = Math.min(1.8, Math.max(0.6, (+v || 100) / 100)); host.style.setProperty("--k", String(k)); if (current) place(); };
  try {
    chrome.storage.local.get({ showVideoButton: true, showImageButton: true, buttonSize: 100 }, s => {
      enabled = !!s.showVideoButton; imagesOn = !!s.showImageButton; setScale(s.buttonSize); check();
    });
    const onStore = (c, area) => {
      if (area !== "local") return;
      if (c.showVideoButton) enabled = !!c.showVideoButton.newValue;
      if (c.showImageButton) imagesOn = !!c.showImageButton.newValue;
      if (c.buttonSize) setScale(c.buttonSize.newValue);
      if (c.showVideoButton || c.showImageButton) { hide(true); check(); }
    };
    chrome.storage.onChanged.addListener(onStore);
    cleanups.push(() => { try { chrome.storage.onChanged.removeListener(onStore); } catch (e) {} });
  } catch (e) {}

  // ------------------------------------------------------------------ UI (shadow DOM, isolated from page CSS)
  const host = document.createElement("chivet-kh-button");
  host.style.cssText = "all:initial;position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647;";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
  <style>
    :host { all: initial; --k: 1; }
    * { box-sizing: border-box; font-family: "Segoe UI", Inter, "Khmer UI", "Noto Sans Khmer", system-ui, sans-serif; }
    .btn { position: fixed; display: flex; align-items: stretch; height: calc(40px * var(--k)); border-radius: calc(11px * var(--k)); user-select: none;
      color: #fff; overflow: hidden; isolation: isolate;
      background: linear-gradient(110deg, #7c5cff 0%, #4f7bff 45%, #22d3ee 100%); background-size: 220% 100%;
      box-shadow: 0 0 0 1px rgba(255,255,255,.28) inset, 0 8px 24px rgba(0,0,0,.45), 0 0 0 0 rgba(124,92,255,.75);
      animation: flow 4s ease-in-out infinite, glow 1.6s ease-out infinite;
      opacity: 0; transform: translateY(-6px) scale(.94); pointer-events: none;
      transition: opacity .16s ease, transform .16s ease, filter .15s; }
    .btn.show { opacity: 1; transform: none; pointer-events: auto; }
    .btn:hover { filter: brightness(1.12) saturate(1.1); }
    .btn::before { content: ""; position: absolute; top: -20%; bottom: -20%; width: 46px; left: -70px; z-index: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,.75), transparent); transform: skewX(-22deg);
      animation: shine 2.6s ease-in-out infinite; pointer-events: none; }
    .btn.ok { background: linear-gradient(110deg, #059669, #10b981, #34d399); animation: none;
      box-shadow: 0 0 0 1px rgba(255,255,255,.3) inset, 0 0 18px rgba(52,211,153,.75); }
    .btn.err { background: linear-gradient(110deg, #b91c1c, #ef4444, #f87171); animation: none; }
    .btn.ok::before, .btn.err::before { display: none; }
    @keyframes shine { 0% { left: -70px; } 55%, 100% { left: calc(100% + 70px); } }
    @keyframes glow { 0% { box-shadow: 0 0 0 1px rgba(255,255,255,.28) inset, 0 8px 24px rgba(0,0,0,.45), 0 0 0 0 rgba(124,92,255,.8); }
                      70% { box-shadow: 0 0 0 1px rgba(255,255,255,.28) inset, 0 8px 24px rgba(0,0,0,.45), 0 0 0 12px rgba(124,92,255,0); }
                      100% { box-shadow: 0 0 0 1px rgba(255,255,255,.28) inset, 0 8px 24px rgba(0,0,0,.45), 0 0 0 0 rgba(124,92,255,0); } }
    @keyframes flow { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
    .main { position: relative; z-index: 1; display: flex; align-items: center; gap: calc(9px * var(--k)); padding: 0 calc(13px * var(--k)) 0 calc(7px * var(--k)); cursor: pointer; }
    .logo { width: calc(27px * var(--k)); height: calc(27px * var(--k)); border-radius: calc(8px * var(--k)); background: #fff; display: grid; place-items: center;
      box-shadow: 0 2px 6px rgba(0,0,0,.25); }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: #34d399; box-shadow: 0 0 8px #34d399;
      animation: blink 1s steps(2, start) infinite; }
    @keyframes blink { to { visibility: hidden; } }
    .label { font-size: calc(13.5px * var(--k)); font-weight: 700; letter-spacing: .2px; white-space: nowrap; text-shadow: 0 1px 2px rgba(0,0,0,.25); }
    .div { position: relative; z-index: 1; width: 1px; background: rgba(255,255,255,.35); margin: 8px 0; }
    .caret, .x { position: relative; z-index: 1; width: calc(30px * var(--k)); display: grid; place-items: center; cursor: pointer; }
    .x { width: calc(26px * var(--k)); opacity: .8; font-size: calc(12px * var(--k)); }
    .caret:hover, .x:hover { background: rgba(0,0,0,.18); }
    .toast { position: fixed; padding: 7px 11px; border-radius: 9px; background: #151821; color: #e7e9f0; font-size: 12.5px;
      border: 1px solid #262b3a; box-shadow: 0 10px 30px rgba(0,0,0,.45); white-space: nowrap; opacity: 0;
      transition: opacity .15s; pointer-events: none; }
    .toast.show { opacity: 1; } .toast.ok { color: #34d399; } .toast.err { color: #f87171; }
    .panel { position: fixed; width: 270px; max-height: 70vh; overflow: auto; background: #151821; color: #e7e9f0;
      border: 1px solid #262b3a; border-radius: 13px; padding: 6px; font-size: 13px; display: none;
      box-shadow: 0 20px 60px rgba(0,0,0,.6); }
    .panel.open { display: block; animation: pop .12s ease; }
    @keyframes pop { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }
    .hdr { padding: 7px 10px 5px; color: #8a91a6; font-size: 10.5px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
    .item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
    .item:hover { background: #7c5cff; color: #fff; }
    .item:hover .sub { color: rgba(255,255,255,.85); }
    .ic { width: 18px; text-align: center; flex: none; }
    .lbl { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sub { color: #8a91a6; font-size: 11.5px; flex: none; }
    .sep { height: 1px; background: #262b3a; margin: 5px 6px; }
    .panel::-webkit-scrollbar { width: 8px; } .panel::-webkit-scrollbar-thumb { background: #2c3244; border-radius: 4px; }
  </style>
  <div class="btn">
    <div class="main" title="Download this video with Chivet-kh Download">
      <span class="logo"><svg style="width:70%;height:70%" viewBox="0 0 64 64">
        <defs><linearGradient id="mdmg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7c5cff"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs>
        <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#mdmg)"/>
        <path d="M32 14v26M21 30l11 11 11-11" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M17 47h30" stroke="#fff" stroke-width="6" stroke-linecap="round"/></svg></span>
      <span class="dot"></span>
      <span class="label">Download this video</span>
    </div>
    <div class="div"></div>
    <div class="caret" title="More options"><svg style="width:43%;height:43%" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></div>
    <div class="x" title="Hide on this video">✕</div>
  </div>
  <div class="toast"></div>
  <div class="panel"></div>`;
  const btn = root.querySelector(".btn");
  const label = root.querySelector(".label");
  const mainBtn = root.querySelector(".main");
  const caretBtn = root.querySelector(".caret");
  const xBtn = root.querySelector(".x");
  const toast = root.querySelector(".toast");
  const panel = root.querySelector(".panel");
  let LABEL = "Download this video";
  let currentKind = "video", currentImg = "";

  function attachHost() {
    const fs = document.fullscreenElement;
    const parent = fs && fs.tagName !== "VIDEO" ? fs : document.documentElement;
    if (parent && host.parentNode !== parent) parent.appendChild(host);
  }

  // ------------------------------------------------------------------ finding the video
  let imgHover = { el: null, t: 0 };
  let current = null, hideTimer = 0, raf = 0, lastX = -1, lastY = -1, lastMove = 0, overUi = false, panelOpen = false;
  const dismissed = new WeakSet();

  const visibleRect = v => {
    const r = v.getBoundingClientRect();
    if (r.width < MIN_W || r.height < MIN_H) return null;
    if (r.bottom < 40 || r.top > innerHeight - 40 || r.right < 40 || r.left > innerWidth - 40) return null;
    const cs = getComputedStyle(v);
    if (cs.visibility === "hidden" || cs.display === "none" || +cs.opacity === 0) return null;
    return r;
  };
  const inside = (r, x, y) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;

  function allVideos() {
    const list = Array.from(document.getElementsByTagName("video"));
    // players that keep the <video> inside a shadow root (Reddit, some news sites)
    for (const el of document.querySelectorAll("shreddit-player, shreddit-player-2, media-player, video-js, mux-player, vds-player")) {
      if (el.shadowRoot) list.push(...el.shadowRoot.querySelectorAll("video"));
    }
    return list;
  }

  function videoAt(x, y) {
    if (x < 0) return null;
    let els = [];
    try { els = document.elementsFromPoint(x, y); } catch (e) {}
    for (const el of els) {
      if (el === host) continue;
      if (el.tagName === "VIDEO" && visibleRect(el)) return el;
      if (el.shadowRoot) {
        try {
          for (const v of el.shadowRoot.querySelectorAll("video")) {
            const r = visibleRect(v);
            if (r && inside(r, x, y)) return v;
          }
        } catch (e) {}
      }
    }
    for (const v of allVideos()) {   // covered by overlays with pointer-events:none
      const r = visibleRect(v);
      if (r && inside(r, x, y)) return v;
    }
    return null;
  }

  // ------------------------------------------------------------------ images
  const IMG_MIN_W = 160, IMG_MIN_H = 120;
  function bestSrc(img) {
    let best = "", bw = 0;
    const ss = img.getAttribute("srcset") || "";
    ss.split(",").forEach(part => {
      const [u, d] = part.trim().split(/\s+/);
      const w = parseFloat(d) || 1;
      if (u && w >= bw) { bw = w; best = u; }
    });
    const pic = img.parentElement && img.parentElement.tagName === "PICTURE" ? img.parentElement : null;
    if (!best && pic) {
      const src = pic.querySelector("source[srcset]");
      if (src) best = src.getAttribute("srcset").split(",").pop().trim().split(/\s+/)[0];
    }
    const cand = [best, img.currentSrc, img.src, img.getAttribute("data-src"), img.getAttribute("data-original")];
    for (const c of cand) {
      if (!c) continue;
      try { const u = new URL(c, location.href).href; if (/^https?:/i.test(u)) return u; } catch (e) {}
    }
    return "";
  }
  function bgUrl(el) {
    const m = /url\(["']?(https?:[^"')]+)["']?\)/.exec(getComputedStyle(el).backgroundImage || "");
    return m ? m[1] : "";
  }
  const bigImg = r => r.width >= IMG_MIN_W && r.height >= IMG_MIN_H && r.bottom > 0 && r.top < innerHeight;

  function imageAt(x, y) {
    if (x < 0) return null;
    let els = [];
    try { els = document.elementsFromPoint(x, y); } catch (e) {}
    for (const el of els.slice(0, 12)) {
      if (el === host || el === document.body || el === document.documentElement) continue;
      if (el.tagName === "IMG") {
        const r = el.getBoundingClientRect(), u = bestSrc(el);
        if (u && bigImg(r)) return { el, url: u };
      } else if (el.tagName !== "VIDEO") {
        const r = el.getBoundingClientRect();
        if (bigImg(r) && r.width < innerWidth * 0.98) {
          const u = bgUrl(el);
          if (u) return { el, url: u };
        }
      }
    }
    for (const img of document.images) {   // images under overlays (Instagram, galleries)
      const r = img.getBoundingClientRect();
      if (inside(r, x, y) && bigImg(r)) {
        const u = bestSrc(img);
        if (u) return { el: img, url: u };
      }
    }
    return null;
  }

  const isPlaying = v => !v.paused && !v.ended && v.readyState >= 2 && v.currentTime > 0;

  // IDM-style: also show on the biggest video that is playing on screen, even without hovering it
  function playingVideo() {
    let best = null, area = 0;
    for (const v of allVideos()) {
      if (!isPlaying(v) || dismissed.has(v)) continue;
      const r = visibleRect(v);
      if (!r) continue;
      const vis = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)) * Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
      if (vis > area) { area = vis; best = v; }
    }
    return best;
  }

  function place() {
    if (!current || !current.isConnected) return hide(true);
    const r = current.getBoundingClientRect();
    if (r.bottom < 30 || r.top > innerHeight - 30 || r.width < MIN_W) return hide(true);
    const bw = btn.offsetWidth || 230, bh = btn.offsetHeight || 40;
    const top = Math.min(Math.max(r.top + 12, 8), innerHeight - bh - 8);
    const left = Math.min(Math.max(r.right - bw - 12, r.left + 8, 8), innerWidth - bw - 8);
    btn.style.top = top + "px";
    btn.style.left = left + "px";
    placeToast();
    if (panelOpen) placePanel();
  }

  function placeToast() {
    const b = btn.getBoundingClientRect();
    const tw = toast.offsetWidth || 200;
    toast.style.top = (b.bottom + 6) + "px";
    toast.style.left = Math.min(Math.max(8, b.right - tw), innerWidth - tw - 8) + "px";
  }

  function placePanel() {
    const b = btn.getBoundingClientRect();
    const pw = 270, ph = panel.offsetHeight || 200;
    let top = b.bottom + 6;
    if (top + ph > innerHeight - 8) top = Math.max(8, b.top - ph - 6);
    panel.style.top = top + "px";
    panel.style.left = Math.min(Math.max(8, b.right - pw), innerWidth - pw - 8) + "px";
  }

  function show(v, kind, imgUrl) {
    clearTimeout(hideTimer); hideTimer = 0;
    if (dismissed.has(v)) return;
    attachHost();
    if (current !== v) {
      current = v;
      currentKind = kind || "video";
      currentImg = imgUrl || "";
      LABEL = currentKind === "image" ? "Download this image" : "Download this video";
      closePanel(); resetState();
    }
    btn.classList.add("show");
    place();
  }

  function hide(now) {
    if (now === true) {
      clearTimeout(hideTimer); hideTimer = 0;
      closePanel(); overUi = false;
      btn.classList.remove("show"); toast.className = "toast"; current = null;
      return;
    }
    if (hideTimer) return;               // already counting down
    hideTimer = setTimeout(() => {
      hideTimer = 0;
      if (overUi || panelOpen) return;
      btn.classList.remove("show"); toast.className = "toast"; current = null;
    }, 1200);
  }

  function check() {
    raf = 0;
    if (!alive) return;
    if (!extOk()) return shutdown();
    if ((!enabled && !imagesOn) || overUi || panelOpen) return;
    const recent = Date.now() - lastMove < 4000;
    const hovered = recent && enabled ? videoAt(lastX, lastY) : null;
    if (hovered && !dismissed.has(hovered)) return show(hovered, "video");
    if (recent && imagesOn) {
      const im = imageAt(lastX, lastY);
      if (im && !dismissed.has(im.el)) {
        if (current === im.el) return show(im.el, "image", im.url);
        if (imgHover.el !== im.el) { imgHover = { el: im.el, t: Date.now() }; }
        if (Date.now() - imgHover.t >= 350) return show(im.el, "image", im.url);
        setTimeout(schedule, 380);
        if (current && currentKind === "image") hide();
        return;
      }
    }
    imgHover = { el: null, t: 0 };
    const v = enabled ? playingVideo() : null;
    if (v) show(v, "video"); else if (current) hide();
  }
  const schedule = () => { if (!raf) raf = requestAnimationFrame(check); };

  const onMove = e => { lastX = e.clientX; lastY = e.clientY; lastMove = Date.now(); schedule(); };
  on(window, "pointermove", onMove, { passive: true, capture: true });
  on(window, "mousemove", onMove, { passive: true, capture: true });
  on(window, "scroll", () => { if (current) place(); schedule(); }, { passive: true, capture: true });
  on(window, "resize", () => { if (current) place(); }, { passive: true });
  on(document, "play", schedule, true);
  on(document, "playing", schedule, true);
  on(document, "fullscreenchange", () => { attachHost(); hide(true); setTimeout(check, 300); }, true);
  const ticker = setInterval(() => { if (!alive) return clearInterval(ticker); if (current) place(); check(); }, 700);
  cleanups.push(() => clearInterval(ticker));

  btn.addEventListener("mouseenter", () => { overUi = true; clearTimeout(hideTimer); hideTimer = 0; });
  btn.addEventListener("mouseleave", () => { overUi = false; if (!panelOpen) hide(); });
  panel.addEventListener("mouseenter", () => { overUi = true; clearTimeout(hideTimer); hideTimer = 0; });
  panel.addEventListener("mouseleave", () => { overUi = false; });
  on(document, "mousedown", e => { if (panelOpen && !e.composedPath().includes(host)) { closePanel(); } }, true);
  on(document, "keydown", e => { if (e.key === "Escape" && panelOpen) closePanel(); }, true);

  mainBtn.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); closePanel(); if (current) downloadDefault(current); });
  caretBtn.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); if (panelOpen) closePanel(); else openPanel(); });
  xBtn.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); if (current) dismissed.add(current); hide(true); });
  for (const t of ["mousedown", "mouseup", "pointerdown", "pointerup", "dblclick", "touchstart"]) {
    btn.addEventListener(t, e => e.stopPropagation());
    panel.addEventListener(t, e => e.stopPropagation());
  }

  // ------------------------------------------------------------------ what to download
  function directSrc(v) {
    const cands = [v.currentSrc, v.src, ...Array.from(v.querySelectorAll("source")).map(s => s.src)];
    return cands.find(u => u && /^https?:/i.test(u)) || "";
  }

  function biggestVideo() {
    let best = null, area = 0;
    for (const v of allVideos()) {
      const r = v.getBoundingClientRect(), a = r.width * r.height;
      if (a > area) { area = a; best = v; }
    }
    return best;
  }

  // Link of one video (null when the page only shows a feed and no link was found)
  function linkFor(v) {
    if (!site) return location.href;
    if (site.strong.test(location.href) && (v === biggestVideo() || /tiktok|youtube/.test(location.hostname))) return location.href;
    let el = v;
    for (let depth = 0; depth < 30 && el; depth++) {
      el = el.parentElement || (el.getRootNode && el.getRootNode().host) || null;
      if (!el || el === document.body || el === document.documentElement) break;
      const anchors = el.querySelectorAll ? el.querySelectorAll("a[href]") : [];
      if (anchors.length > 150) break;
      for (const a of anchors) if (site.strong.test(a.href)) return a.href;
      if (site.weak) for (const a of anchors) if (site.weak.test(a.href)) return a.href;
    }
    if (site.strong.test(location.href)) return location.href;
    return null;
  }

  async function pageUrlFor(v) {
    const link = linkFor(v);
    if (link) return link;
    if (site && site.fb) {
      // Facebook feeds (/reel/?bss=true, /watch, home): read the playing video's id from its video requests
      try {
        const r = await chrome.runtime.sendMessage({ type: "fbid" });
        if (r && r.id) return /\/reel/.test(location.pathname) ? `https://www.facebook.com/reel/${r.id}` : `https://www.facebook.com/watch/?v=${r.id}`;
      } catch (e) {}
    }
    return location.href;
  }

  const cleanTitle = () => (document.title || "video").replace(/^\(\d+\)\s*/, "").replace(/\s*[-|–]\s*(YouTube|Facebook|TikTok|Instagram)\s*$/i, "").trim().slice(0, 90);

  function fileNameFor(url, fallbackExt) {
    try {
      const last = decodeURIComponent(new URL(url).pathname.split("/").pop() || "");
      if (/\.(mp4|webm|m4v|mov|mkv|flv|mp3|m4a|ogg|wav)$/i.test(last) && last.length > 5 &&
          !/^(\d{3,4}p|\d+|index|video|master|play(list)?|media|file|source|default)\.\w+$/i.test(last)) return last;
    } catch (e) {}
    return cleanTitle().replace(/[\\/:*?"<>|]/g, "_") + "." + (fallbackExt || "mp4");
  }

  // ------------------------------------------------------------------ 红果短剧 (hongguoduanju.com)
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const epNumOf = el => {
    const t = ((el.getAttribute && (el.getAttribute("aria-label") || el.getAttribute("title"))) || "").trim();
    const m = /^第\s*(\d+)\s*集$/.exec(t) || /^第\s*(\d+)\s*集$/.exec((el.textContent || "").trim());
    return m ? +m[1] : 0;
  };
  function hgEpisodeButtons() {
    const out = [];
    for (const el of document.querySelectorAll("button, [role=button], li, a")) {
      if (el.closest("chivet-kh-button")) continue;
      const n = epNumOf(el);
      if (n && !out.some(o => o.n === n)) out.push({ n, el });
    }
    return out.sort((a, b) => a.n - b.n);
  }
  function hgRangeTabs() {
    const out = [];
    for (const el of document.querySelectorAll("div, span, li, button")) {
      if (el.childElementCount) continue;
      if (/^\d+\s*-\s*\d+$/.test((el.textContent || "").trim())) out.push(el);
    }
    return out;
  }
  const hgDrama = () => {
    const h = document.querySelector("h1");
    return ((h && h.textContent) || document.title.split(/\s+第\d+集|\s*\|/)[0] || "红果短剧").trim().slice(0, 80);
  };
  function hgEpisode() {
    for (const el of document.querySelectorAll("[aria-pressed='true'], [aria-current], .active, .selected")) {
      const n = epNumOf(el);
      if (n) return n;
    }
    const crumbs = document.querySelectorAll("nav li, [aria-label='面包屑'] li");
    for (let i = crumbs.length - 1; i >= 0; i--) {
      const m = /第\s*(\d+)\s*集/.exec(crumbs[i].textContent || "");
      if (m) return +m[1];
    }
    const m = /第\s*(\d+)\s*集/.exec(document.title);
    return m ? +m[1] : 0;
  }
  const hgName = n => { n = n || hgEpisode(); return hgDrama() + (n ? ` 第${n}集` : ""); };

  // The file the player is showing now (its <video> src, or the newest MP4 the tab loaded after `since`)
  async function hgPlayingFile(since) {
    const v = biggestVideo();
    const src = v ? directSrc(v) : "";
    if (src && !/\.(m3u8|mpd)(\?|$)/i.test(src)) return src;
    const files = (await tabStreams()).filter(s => s.kind === "file" && (!since || s.ts >= since));
    return files.length ? files[0].url : "";
  }

  // Click through the episode list and note each episode's file. Locked / VIP episodes do not start a new file
  // and are skipped — nothing is unlocked. Stops after 3 locked episodes in a row.
  let hgBusy = false;
  async function hgCollectEpisodes(report) {
    if (hgBusy) return { links: [], skipped: 0, busy: true };
    hgBusy = true;
    const links = [], tried = new Set();
    let skipped = 0, misses = 0, prev = await hgPlayingFile(0);
    const vid = biggestVideo(), wasMuted = vid ? vid.muted : false;
    try {
      const cur = hgEpisode();
      if (prev && cur) { links.push({ url: prev, text: hgName(cur) }); tried.add(cur); }
      const tabs = hgRangeTabs();
      outer:
      for (const tab of (tabs.length ? tabs : [null])) {
        if (tab) { tab.click(); await sleep(700); }
        for (const { n, el } of hgEpisodeButtons()) {
          if (tried.has(n)) continue;
          tried.add(n);
          report && report(n, links.length);
          const t0 = Date.now();
          el.click();
          let url = "";
          for (let k = 0; k < 16 && !url; k++) {
            await sleep(500);
            const v = biggestVideo();
            if (v) v.muted = true;
            const f = await hgPlayingFile(t0);
            if (f && f !== prev && !links.some(l => l.url === f)) url = f;
          }
          if (url) { links.push({ url, text: hgName(n) }); prev = url; misses = 0; }
          else {
            skipped++; misses++;
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
            if (misses >= 3) break outer;
          }
        }
      }
    } finally {
      hgBusy = false;
      const v = biggestVideo();
      if (v) { v.muted = wasMuted; try { v.pause(); } catch (e) {} }
    }
    return { links, skipped };
  }

  async function hgDownloadAll() {
    closePanel();
    let r = null;
    try {
      r = await chrome.runtime.sendMessage({ type: "ping" });
      if (!(r && r.ok)) launchApp();   // still inside the click → Chrome lets us open the app
    } catch (e) { setState("err", "Reload this page (F5)", 4000); return; }
    setState("", "Reading episodes…", 0);
    const res = await hgCollectEpisodes((n, got) => {
      setState("", `Episode ${n} · ${got} found…`, 0);
      showToast(`Chivet-kh: reading episode ${n} · ${got} found`, "", 0);
    });
    if (!res.links.length) { setState("err", "No free episode found", 4000); showToast("No free episode found", "err", 4000); return; }
    try {
      r = await chrome.runtime.sendMessage({ type: "episodes", page: location.href, title: hgDrama(), ...res });
    } catch (e) { r = null; }
    if (r && r.ok) {
      setState("ok", `✓ ${res.links.length} episodes sent`, 3000);
      showToast(`✓ ${res.links.length} episodes sent to Chivet-kh` + (res.skipped ? ` · ${res.skipped} locked / VIP skipped` : ""), "ok", 6000);
    } else {
      const t = r && r.reason === "offline" ? "Open Chivet-kh app first" : "Not accepted";
      setState("err", t, 4000);
      showToast(t, "err", 5000);
    }
  }

  const fmtSize = n => !n ? "" : n < 1048576 ? (n / 1024).toFixed(0) + " KB" : n < 1073741824 ? (n / 1048576).toFixed(1) + " MB" : (n / 1073741824).toFixed(2) + " GB";

  // ------------------------------------------------------------------ feedback
  let toastTimer = 0, stateTimer = 0;
  function resetState() {
    clearTimeout(stateTimer);
    btn.classList.remove("ok", "err");
    label.textContent = LABEL;
  }
  function showToast(text, cls, ms) {
    clearTimeout(toastTimer);
    toast.textContent = text;
    toast.className = "toast show " + (cls || "");
    placeToast();
    if (ms) toastTimer = setTimeout(() => { toast.className = "toast"; }, ms);
  }
  function setState(cls, text, ms) {
    clearTimeout(stateTimer);
    btn.classList.remove("ok", "err");
    if (cls) btn.classList.add(cls);
    label.textContent = text;
    place();
    if (ms) stateTimer = setTimeout(() => { resetState(); place(); }, ms);
  }

  // Open the desktop app through its chivetkh:// link. This runs inside the user's click, which Chrome
  // requires before it lets a page open an app on the computer.
  function launchApp() {
    try {
      const a = document.createElement("a");
      a.href = "chivetkh://start";
      a.style.display = "none";
      (document.body || document.documentElement).appendChild(a);
      a.click();
      setTimeout(() => a.remove(), 1000);
    } catch (e) {}
  }

  async function send(payload) {
    closePanel();
    setState("", payload.lookup ? "Opening Chivet-kh…" : "Sending…", 0);
    const msg = { type: "send", referrer: location.href, title: cleanTitle(), noLaunch: true, ...payload };
    let r = null;
    try {
      r = await chrome.runtime.sendMessage(msg);
      if (r && r.reason === "offline" && r.autoLaunch !== false) {
        setState("", "Starting Chivet-kh app…", 0);
        showToast("Starting the app… if Chrome asks “Open Chivet-kh Download?”, tick Always allow → Open", "", 9000);
        launchApp();
        const w = await chrome.runtime.sendMessage({ type: "waitApp", ms: 30000 });
        if (w && w.ok) r = await chrome.runtime.sendMessage(msg);
      }
    } catch (e) {
      setState("err", "Reload this page (F5)", 4000);
      return;
    }
    if (r && r.ok) setState("ok", payload.lookup ? "✓ Opened in Chivet-kh" : payload.kind === "image" ? "✓ Saved" : "✓ Sent to Chivet-kh", 2200);
    else if (r && r.reason === "offline") { setState("err", "Open Chivet-kh app first", 4000); showToast("Could not start the app — open Chivet-kh Download once, then click again", "err", 5000); }
    else setState("err", "Not accepted", 3500);
  }

  async function tabStreams() {
    try {
      const r = await chrome.runtime.sendMessage({ type: "streams" });
      return (r && r.streams) || [];
    } catch (e) {
      return [];
    }
  }

  function imageName(url) {
    try {
      const last = decodeURIComponent(new URL(url).pathname.split("/").pop() || "");
      if (/\.(jpe?g|png|gif|webp|avif|bmp|svg|heic|tiff?)$/i.test(last)) return last.slice(-120);
    } catch (e) {}
    return "";  // the app picks the name and extension from the server's answer
  }

  function downloadImage(url) {
    const name = imageName(url);
    return send({ url, mode: "http", quick: true, kind: "image", ...(name ? { filename: name } : {}) });
  }

  async function downloadDefault(v) {
    if (currentKind === "image" && v === current) return downloadImage(currentImg);
    const src = directSrc(v);
    if (HG) {
      const file = await hgPlayingFile(0);
      return send({ url: file || location.href, mode: "ytdlp", lookup: true, title: hgName() });
    }
    if (site) return send({ url: await pageUrlFor(v), mode: "ytdlp", lookup: true });
    if (src && !/\.(m3u8|mpd)(\?|$)/i.test(src)) return send({ url: src, mode: "http", filename: fileNameFor(src) });
    if (src) return send({ url: src, mode: "ytdlp", lookup: true });
    const streams = await tabStreams();
    const stream = streams.find(s => s.kind !== "file");
    if (stream) return send({ url: stream.url, mode: "ytdlp", lookup: true });
    const file = streams.find(s => s.kind === "file");
    if (file) return send({ url: file.url, mode: "http", filename: fileNameFor(file.url) });
    return send({ url: location.href, mode: "ytdlp", lookup: true });
  }

  function addItem(icon, text, sub, onClick) {
    const d = document.createElement("div");
    d.className = "item";
    d.innerHTML = `<span class="ic"></span><span class="lbl"></span><span class="sub"></span>`;
    d.querySelector(".ic").textContent = icon;
    d.querySelector(".lbl").textContent = text;
    d.querySelector(".sub").textContent = sub || "";
    d.title = text;
    d.addEventListener("click", e => { e.stopPropagation(); onClick(); });
    panel.appendChild(d);
  }
  const addHdr = t => { const d = document.createElement("div"); d.className = "hdr"; d.textContent = t; panel.appendChild(d); };
  const addSep = () => { const d = document.createElement("div"); d.className = "sep"; panel.appendChild(d); };

  async function openPanel() {
    if (!current) return;
    const v = current;
    panel.innerHTML = "";
    addHdr("Chivet-kh Download");
    if (currentKind === "image") {
      const u = currentImg;
      addItem("⬇", "Download this image", "", () => downloadImage(u));
      addItem("▦", "Download all images on this page…", "", async () => {
        closePanel();
        setState("", "Collecting images…", 0);
        let r = null;
        try { r = await chrome.runtime.sendMessage({ type: "grab", which: "images" }); } catch (e) {}
        if (r && r.ok) setState("ok", `✓ ${r.count} images found`, 2500);
        else setState("err", r && r.reason === "offline" ? "Open Chivet-kh app first" : "Could not collect", 3500);
      });
      addSep();
      addItem("✕", "Hide on this image", "", () => { dismissed.add(v); hide(true); });
      panel.classList.add("open");
      panelOpen = true;
      placePanel();
      return;
    }
    addItem("⬇", HG ? "Download this episode…" : "Download this video…", "", () => downloadDefault(v));
    if (HG) {
      addItem("▶▶", "Download all free episodes…", "", hgDownloadAll);
    } else if (site) {
      addItem("♪", "Audio only (MP3)…", "", async () => send({ url: await pageUrlFor(v), mode: "ytdlp", lookup: true }));
    } else {
      const src = directSrc(v);
      addItem("◎", "Find formats on this page…", "", () => send({ url: location.href, mode: "ytdlp", lookup: true }));
      const streams = (await tabStreams()).filter(s => s.url !== src);
      if (streams.length) {
        addSep();
        addHdr("Detected on this page");
        for (const s of streams.slice(0, 12)) {
          const name = fileNameFor(s.url, s.kind === "file" ? (s.ctype.split("/")[1] || "mp4").replace("mpeg", "mp3") : "mp4");
          if (s.kind === "file") addItem("⬇", name, fmtSize(s.size), () => send({ url: s.url, mode: "http", filename: name }));
          else addItem("≋", (s.kind === "hls" ? "HLS stream · " : "DASH stream · ") + (new URL(s.url).pathname.split("/").pop() || "playlist"),
            s.kind.toUpperCase(), () => send({ url: s.url, mode: "ytdlp", lookup: true }));
        }
      }
    }
    addSep();
    addItem("▦", "Grab all files on this page…", "", async () => {
      closePanel();
      setState("", "Collecting files…", 0);
      let r = null;
      try { r = await chrome.runtime.sendMessage({ type: "grab", which: "all" }); } catch (e) {}
      if (r && r.ok) setState("ok", `✓ ${r.count} files sent`, 2500);
      else setState("err", r && r.reason === "offline" ? "Open Chivet-kh app first" : "Could not collect", 3500);
    });
    addItem("▶", "Download all videos on this page…", "", async () => {
      closePanel();
      setState("", "Collecting video links…", 0);
      let r = null;
      try { r = await chrome.runtime.sendMessage({ type: "links", scrolls: 15 }); } catch (e) {}
      if (r && r.ok) setState("ok", `✓ ${r.count} videos found`, 2500);
      else setState("err", r && r.reason === "none" ? "No video links here" : r && r.reason === "offline" ? "Open Chivet-kh app first" : "Could not collect", 3500);
    });
    addItem("✕", "Hide on this video", "", () => { dismissed.add(v); hide(true); });
    panel.classList.add("open");
    panelOpen = true;
    placePanel();
  }

  function closePanel() {
    panel.classList.remove("open");
    panelOpen = false;
  }

  // ------------------------------------------------------------------ status for the popup
  const onMsg = (msg, _s, reply) => {
    if (msg && msg.type === "mdm-status") {
      reply({ ok: true, frame: location.href, videos: allVideos().length, enabled });
    } else if (msg && msg.type === "mdm-hg-episodes" && HG && window === window.top) {
      hgCollectEpisodes((n, got) => showToast(`Chivet-kh: episode ${n} · ${got} found…`, "", 0))
        .then(res => { showToast(`Chivet-kh: ${res.links.length} episodes found`, "ok", 4000); reply({ ...res, title: hgDrama() }); });
      return true;
    }
  };
  try {
    chrome.runtime.onMessage.addListener(onMsg);
    cleanups.push(() => { try { chrome.runtime.onMessage.removeListener(onMsg); } catch (e) {} });
  } catch (e) {}

  check();
})();
