const $ = (id) => document.getElementById(id);

function setMsg(text, cls = "") {
  const m = $("msg");
  m.textContent = text;
  m.className = "msg " + cls;
}

async function refreshStatus() {
  const s = await mdmSettings();
  const ok = !!(await mdmPing(s.port));
  $("status").className = "status " + (ok ? "ok" : "off");
  $("statusText").textContent = ok ? `Connected · port ${s.port}` : "App not running";
  $("startApp").style.display = ok ? "none" : "";
  return ok;
}

async function load() {
  const s = await mdmSettings();
  $("enabled").checked = s.enabled;
  $("showVideoButton").checked = s.showVideoButton;
  $("showImageButton").checked = s.showImageButton;
  $("autoLaunch").checked = s.autoLaunch;
  $("buttonSize").value = s.buttonSize;
  $("buttonSizeVal").textContent = s.buttonSize + "%";
  $("port").value = s.port;
  $("minSize").value = s.minSizeKB;
  $("captureAll").checked = s.captureAll;
  $("sendCookies").checked = s.sendCookies;
  $("exts").value = s.exts;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    $("sendPage").dataset.url = tab && tab.url ? tab.url : "";
  } catch (e) {}
  await refreshStatus();
  await checkTab();
  if (await refreshUpdates()) pollUpdates();
}

// ---------------- Updates & helpers: one click → the app downloads and installs it
let updTimer = 0;
async function refreshUpdates() {
  const card = $("updCard"), list = $("updList");
  const st = await mdmStatus();
  if (!st) { card.style.display = "none"; return; }
  const rows = [];
  const mine = chrome.runtime.getManifest().version;
  if (mdmNewer(st.extension_version, mine)) {
    rows.push({ id: "ext", name: "Browser extension", why: `Version ${st.extension_version} is ready (you have ${mine})`,
                need: true, action: "reload" });
  }
  if (st.restart_needed) rows.push({ id: "restart", name: "Restart Chivet-kh Download", why: "Finishes the last update", need: true, action: "restart" });
  for (const c of st.components) rows.push(c);
  const needs = rows.filter(r => r.need || r.state === "running" || r.state === "error" || r.state === "done");
  card.style.display = "";
  $("updCount").textContent = rows.filter(r => r.need).length || "";
  $("updCount").style.display = rows.some(r => r.need) ? "" : "none";
  list.innerHTML = "";
  const show = needs.length ? needs : [{ id: "all", name: "Everything is up to date", why: `App ${st.version} · yt-dlp ${(st.components.find(c => c.id === "ytdlp") || {}).version || ""}`, ok: true }];
  for (const r of show) {
    const row = document.createElement("div");
    row.className = "upd";
    const info = document.createElement("div");
    info.className = "info";
    info.innerHTML = `<div class="nm"></div><div class="why"></div>`;
    info.querySelector(".nm").textContent = r.name + (r.latest && r.need ? `  →  ${r.latest}` : "");
    const why = info.querySelector(".why");
    why.textContent = r.state === "running" ? (r.msg || "Working…") : r.state === "error" ? "✖ " + r.msg : r.state === "done" ? r.msg : r.why;
    if (r.state === "error") why.classList.add("err");
    if (r.state === "running") info.insertAdjacentHTML("beforeend", `<div class="bar"><i style="width:${r.pct || 3}%"></i></div>`);
    row.appendChild(info);
    if (r.ok || (r.state === "done" && !r.need)) {
      const ok = document.createElement("span"); ok.className = "ok"; ok.textContent = "✓"; row.appendChild(ok);
    } else if (r.need && r.state !== "running") {
      const b = document.createElement("button");
      b.className = "primary";
      b.textContent = r.action === "update" ? "Update" : r.action === "reload" ? "Reload" : r.action === "restart" ? "Restart" : r.state === "error" ? "Retry" : "Install";
      b.onclick = async () => {
        b.disabled = true; b.textContent = "…";
        if (r.action === "reload") { chrome.runtime.reload(); return; }
        if (r.action === "restart") await mdmPost("/restart");
        else await mdmPost("/install", { id: r.id });
        pollUpdates();
      };
      row.appendChild(b);
    }
    list.appendChild(row);
  }
  $("updNote").textContent = "";
  chrome.runtime.sendMessage({ type: "badge" });
  return rows.some(r => r.state === "running") || st.restart_needed;
}

function pollUpdates() {
  clearTimeout(updTimer);
  updTimer = setTimeout(async () => {
    const busy = await refreshUpdates().catch(() => false);
    if (busy) pollUpdates();
    else if (!(await mdmStatus())) { $("updNote").textContent = "Restarting the app…"; pollUpdates(); }
  }, 1000);
}

$("updCheck").addEventListener("click", async () => {
  $("updNote").textContent = "Checking GitHub…";
  await mdmPost("/check-updates");
  setTimeout(refreshUpdates, 2500);
});

// Is the video button running on this tab? Offer a fix when it is not.
async function checkTab() {
  const d = $("diag");
  d.className = "diag";
  d.textContent = "";
  let tab;
  try { [tab] = await chrome.tabs.query({ active: true, currentWindow: true }); } catch (e) {}
  if (!tab || !/^https?:/i.test(tab.url || "")) { d.textContent = "Open a web page with a video to use the button."; return; }
  let allowed = true;
  try { allowed = await chrome.permissions.contains({ origins: [new URL(tab.url).origin + "/*"] }); } catch (e) {}
  if (!allowed) {
    d.className = "diag warn";
    d.innerHTML = "<span>Site access is off for this site.</span>";
    const b = document.createElement("button");
    b.textContent = "Allow on all sites";
    b.onclick = async () => {
      const ok = await chrome.permissions.request({ origins: ["<all_urls>"] }).catch(() => false);
      if (ok) { await chrome.runtime.sendMessage({ type: "inject", tabId: tab.id }); checkTab(); }
    };
    d.appendChild(b);
    return;
  }
  let st = null;
  try { st = await chrome.tabs.sendMessage(tab.id, { type: "mdm-status" }); } catch (e) {}
  if (st && st.ok) {
    d.className = "diag ok";
    d.textContent = `● Button active on this page · ${st.videos} video${st.videos === 1 ? "" : "s"} found`;
    return;
  }
  d.className = "diag warn";
  d.innerHTML = "<span>Button not running on this page.</span>";
  const b = document.createElement("button");
  b.textContent = "Activate now";
  b.onclick = async () => {
    const r = await chrome.runtime.sendMessage({ type: "inject", tabId: tab.id });
    if (r && r.ok) setTimeout(checkTab, 300);
    else { d.className = "diag warn"; d.textContent = "Could not activate — press F5 on the page."; }
  };
  d.appendChild(b);
}

async function send(url, mode) {
  if (!/^https?:\/\//i.test(url || "")) {
    setMsg("Enter an http(s) link first.", "err");
    return;
  }
  if (!(await refreshStatus())) setMsg("Starting Chivet-kh Download…");
  const r = await chrome.runtime.sendMessage({ type: "send", url, mode, lookup: mode === "ytdlp" });
  setMsg(r && r.ok ? "Sent to Chivet-kh Download ✓" : "The app did not accept the link.", r && r.ok ? "ok" : "err");
}

$("enabled").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ enabled: e.target.checked });
  chrome.runtime.sendMessage({ type: "badge" });
  setMsg(e.target.checked ? "Capturing browser downloads." : "Browser downloads stay in the browser.");
});

$("startApp").addEventListener("click", async () => {
  const a = document.createElement("a");
  a.href = "chivetkh://start";
  document.body.appendChild(a);
  a.click();
  a.remove();
  $("statusText").textContent = "Starting…";
  const r = await chrome.runtime.sendMessage({ type: "waitApp", ms: 30000 });
  await refreshStatus();
  setMsg(r && r.ok ? "Chivet-kh Download is running ✓" : "Could not start it — open the app once from its folder.", r && r.ok ? "ok" : "err");
});

$("showVideoButton").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ showVideoButton: e.target.checked });
  setMsg(e.target.checked ? "Video button on — hover any video." : "Video button hidden.");
});

$("showImageButton").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ showImageButton: e.target.checked });
  setMsg(e.target.checked ? "Image button on — hover any picture." : "Image button hidden.");
});

$("buttonSize").addEventListener("input", async (e) => {
  const v = parseInt(e.target.value, 10) || 100;
  $("buttonSizeVal").textContent = v + "%";
  await chrome.storage.local.set({ buttonSize: v });   // open pages update at once
});

$("autoLaunch").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ autoLaunch: e.target.checked });
  setMsg(e.target.checked ? "The app will start by itself when needed." : "Auto-start off.");
});

$("sendLink").addEventListener("click", () => send($("url").value.trim(), "auto"));
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") send($("url").value.trim(), "auto"); });
$("allVideos").addEventListener("click", async () => {
  let tab;
  try { [tab] = await chrome.tabs.query({ active: true, currentWindow: true }); } catch (e) {}
  if (!tab || !/^https?:/i.test(tab.url || "")) { setMsg("Open a page with videos first.", "err"); return; }
  setMsg("Scrolling the page and collecting video links… (up to 20 s)");
  const r = await chrome.runtime.sendMessage({ type: "links", tabId: tab.id, scrolls: 15 });
  if (r && r.ok) setMsg(`Found ${r.count} videos — choose them in Chivet-kh ✓`, "ok");
  else setMsg(r && r.reason === "none" ? "No video links found on this page." :
              r && r.reason === "offline" ? "Open the Chivet-kh Download app first." : "Could not read this page.", "err");
});

$("grabAll").addEventListener("click", async () => {
  let tab;
  try { [tab] = await chrome.tabs.query({ active: true, currentWindow: true }); } catch (e) {}
  if (!tab || !/^https?:/i.test(tab.url || "")) { setMsg("Open a web page first.", "err"); return; }
  setMsg("Collecting files…");
  const r = await chrome.runtime.sendMessage({ type: "grab", tabId: tab.id, which: "all" });
  if (r && r.ok) setMsg(`Sent ${r.count} files — choose them in Chivet-kh Download ✓`, "ok");
  else setMsg(r && r.reason === "offline" ? "Open the Chivet-kh Download app first." : "Could not read this page.", "err");
});

$("sendPage").addEventListener("click", () => send($("sendPage").dataset.url, "ytdlp"));

$("save").addEventListener("click", async () => {
  const port = parseInt($("port").value, 10);
  await chrome.storage.local.set({
    port: port >= 1024 && port <= 65535 ? port : MDM_DEFAULTS.port,
    minSizeKB: Math.max(0, parseInt($("minSize").value, 10) || 0),
    captureAll: $("captureAll").checked,
    sendCookies: $("sendCookies").checked,
    exts: $("exts").value.trim()
  });
  setMsg("Settings saved.", "ok");
  refreshStatus();
});

$("reset").addEventListener("click", async () => {
  await chrome.storage.local.set({ ...MDM_DEFAULTS });
  await load();
  setMsg("Defaults restored.", "ok");
});

load();
