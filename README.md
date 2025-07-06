# 🎵 YouTube 音樂播放器

這是一款基於 Python 和 PyQt5 打造的桌面音樂播放器，支援播放 YouTube 音訊，整合播放清單管理、AI 標題解析、歌詞查詢與系統托盤控制等功能。可同時播放線上與本地音訊，支援 `.m3u` / `.txt` 播放清單。

---

## ✨ 功能特色

- 🔗 **多種播放來源支援**：
  - ✅ YouTube 影片、播放清單、頻道網址
  - ✅ 本地音訊檔案（`.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`）
  - ✅ `.m3u` / `.txt` 播放清單匯入

- 🎶 **播放清單管理**：
  - 支援儲存 / 匯出 `.m3u` 格式
  - 可清除 / 隨機 / 循環播放

- 🔍 **關鍵字搜尋**：
  - 前 5 筆搜尋結果供使用者選擇加入播放清單

- 🧠 **AI 智慧標題辨識 + 歌詞搜尋**：
  - 利用 AI 分析影片名稱取得真實歌名
  - 自動搜尋 Genius 歌詞頁面

- 🎧 **播放功能完整**：
  - 播放、暫停、上下首、音量調整
  - VLC 串流播放，自動備援下載音訊檔播放
  - 系統托盤控制（可縮小至通知區）

---

## 📥 安裝方式

### ✅ 安裝執行檔（建議使用者方式）

1. 前往 [Releases](https://github.com/Jenne14294/MusicPlayer/releases) 下載 `.zip`
2. 解壓後執行 `Youtube Player.exe` 即可使用（無需安裝）

## 📝 播放清單格式說明

### `.m3u` 播放清單範例：
```
#EXTM3U
#EXTINF:-1,歌曲名稱1
https://www.youtube.com/watch?v=xxxxxx1
#EXTINF:-1,歌曲名稱2
https://www.youtube.com/watch?v=xxxxxx2
```

### `.txt` 播放清單範例：
```
https://www.youtube.com/watch?v=xxxxxx1
https://www.youtube.com/watch?v=xxxxxx2
```

---

## 🔧 技術說明

| 功能項目         | 使用技術          |
|------------------|-------------------|
| 圖形介面         | PyQt5             |
| YouTube 資訊擷取 | yt_dlp            |
| 音訊播放         | python-vlc        |
| 串流備援下載     | ffmpeg            |
| AI 歌名辨識      | Gemini API        |
| 歌詞查詢         | Genius API        |
| 系統托盤         | QSystemTrayIcon   |

⚠️ **注意：需要安裝 VLC 播放器（建議安裝官方版 VLC，python-vlc 會呼叫 VLC 執行檔）**

---

## 📄 授權 License

本專案使用 [MIT License](https://opensource.org/licenses/MIT)，可自由使用、修改與發佈。
但須先通知告知原作者

---

## 🙋‍♀️ 聯絡與參與貢獻

若你有建議、發現 bug，或想參與改進，歡迎透過：

- 開 issue 留言
- 發送 Pull Request
- 或直接聯絡開發者 🙌

