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
}

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
