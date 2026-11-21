# Chivet-kh Download

A fast download manager for Windows with a Chrome/Edge extension — multi-connection downloads, a **"Download this video"** button on Facebook, YouTube, TikTok, Instagram and more, a **"Download this image"** button, and **"Grab all files on this page"**.

Built with Python + PyQt6, yt-dlp and ffmpeg.

> 🇰🇭 ការណែនាំជាភាសាខ្មែរ នៅខាងក្រោម

## Features

- **Fast downloads** — up to 32 connections per file, pause / resume, queue, scheduler, speed limiter
- **Video button** — glowing *Download this video* button on any playing video (Facebook Reels, YouTube, TikTok, Instagram, X, Vimeo, ordinary sites, HLS/m3u8 streams)
- **Download video from a page** — pick 1080p / 720p MP4, original audio or MP3 (VBR / 320 / 256 / 192 / 128 kbps), subtitles
- **Image button** — hover any picture, one click saves the full-size image
- **Grab all files on this page** — every image, video, audio, document, archive and program on a page, filter by type and tick what you want
- **Browser capture** — zip, exe, pdf, mp4… downloads started in Chrome go to Chivet-kh Download automatically
- **Download links** — paste many Reel / video / playlist / channel / page links; every video inside them is listed and downloaded (quality, MP3, subtitles for all at once)
- **红果短剧 (hongguoduanju.com)** — built-in reader: *Download this episode* on the playing video, or *▾ → Download all free episodes* (clicks through the episode list; locked / VIP episodes are skipped, nothing is unlocked)
- **Download all videos on this page** — the extension scrolls a page (e.g. a Facebook page's Reels tab, a YouTube channel, a TikTok profile), collects every video link and sends them to *Download links*
- **Subtitles** — choose a language or *All languages*, put them into the video, or download *Subtitles only (.srt)*
- **Button size** — make the video/image button smaller or bigger in the extension popup
- Progress window with per-connection view, *Download complete* window, categories, dark UI, system tray
- Optional BitTorrent (`pip install libtorrent`)

## Install (Windows)

### Option 1 — ready-made .exe
Download the latest **ChivetKhDownload.zip** from [Releases](../../releases), unzip it and run `ChivetKhDownload.exe`.

### Option 2 — from source
1. Install [uv](https://docs.astral.sh/uv/): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Download this repository (Code → Download ZIP) and unzip it
3. Double-click **`run_uv.bat`** — the first start installs Python 3.12 and everything else (1–2 minutes)

## Add the browser extension (Chrome / Edge)

1. Open `chrome://extensions` (Edge: `edge://extensions`)
2. Turn on **Developer mode**
3. Click **Load unpacked** and choose the **`browser_extension`** folder
4. Pin the extension — its popup shows **● Connected** while Chivet-kh Download is running

## How to use

1. Keep Chivet-kh Download running (it can sit in the system tray)
2. Play or hover a video → click **Download this video** → choose the quality → **Download Now**
3. Hover an image → **Download this image**
4. Right-click a page → **Download all files on this page (Chivet-kh Download)**
5. Files are saved in `Downloads\ChivetKhDownload\` — sorted into Video, Images, Music, Programs…

Chivet-kh Download starts with Windows (hidden in the tray). If it is closed, clicking a download button starts it automatically — the first time Chrome asks *"Open Chivet-kh Download?"*: tick **Always allow** and click **Open**.

**One-click updates:** when something needs installing or updating (Deno, yt-dlp, ffmpeg, a new Chivet-kh version, the extension), the extension icon shows an orange **!** — open it and press **Install** / **Update**. The app downloads it, installs it and restarts by itself.

**YouTube** needs a small free helper called **Deno**: the app offers to install it the first time (or *Helpers… → Install Deno*).

If a site stops working, open **Helpers… → Update yt-dlp** (works in the .exe too) in the *Download video from a page* window.

## Build the .exe yourself

Double-click **`build_exe.bat`** → the result is in `dist\ChivetKhDownload\` (the `browser_extension` folder is copied next to the exe).

## Notes

- Downloads use your own browser session (cookies), so you can save what you can already watch while logged in.
- DRM-protected streaming services (Netflix, Disney+, paid movie platforms…) cannot be downloaded.
- Please respect copyright and each site's terms of use.
- The local API listens only on `127.0.0.1:17890` and accepts requests only from the extension.

---

## 🇰🇭 ការណែនាំជាភាសាខ្មែរ

**Chivet-kh Download** ជាកម្មវិធីទាញឯកសារលឿន សម្រាប់ Windows ដែលមាន extension សម្រាប់ Chrome/Edge។

### ដំឡើង
1. ដំឡើង uv៖ `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. ទាញ repository នេះ (Code → Download ZIP) ហើយពន្លា
3. ចុចពីរដងលើ **`run_uv.bat`** (លើកទីមួយចំណាយពេល 1–2 នាទី)

ឬទាញ **ChivetKhDownload.exe** ពី [Releases](../../releases) ហើយបើកវាដោយផ្ទាល់។

### ដាក់ Extension
បើក `chrome://extensions` → បើក **Developer mode** → ចុច **Load unpacked** → ជ្រើសថត **`browser_extension`**

### របៀបប្រើ
- **វីដេអូ**៖ ចាក់ ឬដាក់កណ្ដុរលើវីដេអូ → ចុច **Download this video** → ជ្រើស 1080p / 720p / MP3 → **Download Now**
- **រូបភាព**៖ ដាក់កណ្ដុរលើរូបភាព → **Download this image** (រក្សាទុកភ្លាមក្នុង Images)
- **Links** (ប៊ូតុងលើរបារឧបករណ៍)៖ បិទភ្ជាប់ Link Reel, Link Page, Playlist, Channel ច្រើនក្នុងពេលតែមួយ → **Find videos** → **Download** វីដេអូទាំងអស់
- **ចុចកណ្ដុរស្ដាំលើទំព័រ → Download all videos on this page**៖ វារមូរទំព័រ (ឧ. ផ្ទាំង Reels របស់ Page) ហើយប្រមូល Link វីដេអូទាំងអស់
- **Subtitle**៖ ជ្រើសភាសា ឬ All languages, ដាក់ចូលក្នុងវីដេអូ, ឬទាញតែ Subtitle (.srt)
- **ទំហំប៊ូតុង**៖ ចុចរូប extension → រំកិល **Button size**
- **ទាញទាំងអស់**៖ ចុចកណ្ដុរស្ដាំលើទំព័រ → **Download all files on this page**
- **ឯកសារធម្មតា** (zip, exe, pdf…)៖ ចុចទាញក្នុង Chrome ធម្មតា វាមកក្នុងកម្មវិធីដោយខ្លួនឯង
- ឯកសារទាំងអស់នៅក្នុង `Downloads\ChivetKhDownload\`
- កម្មវិធីបើកដោយខ្លួនឯងពេលបើកកុំព្យូទ័រ (លាក់ក្នុង tray)។ បើវាបិទ ចុចប៊ូតុងទាញ វានឹងបើកកម្មវិធីឲ្យ — លើកដំបូង Chrome សួរ *"Open Chivet-kh Download?"* → ធីក **Always allow** → ចុច **Open**
- **Update ចុចតែម្ដង៖** ពេលមានអ្វីត្រូវដំឡើង ឬ Update (Deno, yt-dlp, ffmpeg, version ថ្មី, extension) រូប extension បង្ហាញ **!** ពណ៌ទឹកក្រូច → ចុចរូប extension → ចុច **Install** / **Update** → កម្មវិធីទាញ ដំឡើង និងបិទបើកឡើងវិញដោយខ្លួនឯង
- **YouTube** ត្រូវការកម្មវិធីជំនួយ **Deno** (ឥតគិតថ្លៃ)៖ កម្មវិធីនឹងសួរដំឡើងឲ្យលើកដំបូង ឬ **Helpers… → Install Deno**
- **红果短剧**៖ បើកភាគនៅ Chrome ឲ្យវាចាក់ → ចុចប៊ូតុង *Download this episode* ឬ **▾ → Download all free episodes** ដើម្បីទាញគ្រប់ភាគឥតគិតថ្លៃ (ភាគជាប់សោ/VIP រំលង)
- បើទាញពី Facebook/YouTube មិនបាន៖ **Helpers… → Update yt-dlp** ហើយបិទបើកកម្មវិធីឡើងវិញ

### ចំណាំ
- វីដេអូដែលមាន DRM (Netflix, Disney+…) មិនអាចទាញបានទេ
- សូមគោរពសិទ្ធិអ្នកនិពន្ធ និងលក្ខខណ្ឌរបស់វេបសាយនីមួយៗ
