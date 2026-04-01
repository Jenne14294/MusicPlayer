import sys
import random
import time
import os
import vlc
import json
import requests
import urllib.parse
import webbrowser
import PyQt5

# 1. 取得 PyQt5 套件的安裝路徑
pyqt_path = os.path.dirname(PyQt5.__file__)

# 2. 組合出正確的插件路徑
# PyQt5 的插件通常藏在 site-packages/PyQt5/Qt5/plugins
plugin_path = os.path.join(pyqt_path, 'Qt5', 'plugins', 'platforms')

# 3. 強制設定環境變數
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

# --- 測試：確保路徑是真的存在的 ---
if not os.path.exists(os.path.join(plugin_path, 'qwindows.dll')):
	print(f"⚠️ 警告：找不到 qwindows.dll，路徑可能不正確：{plugin_path}")
else:
	print(f"✅ 成功鎖定 Qt 插件路徑")


from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QListWidget, QLabel, QSlider, QStyle, QGridLayout, QSystemTrayIcon, QMenu, QAction, QWidgetAction, QHBoxLayout, QMessageBox, QDialog, QVBoxLayout, QListWidgetItem, QFileDialog, QSizePolicy, QTextBrowser, QComboBox, QTextEdit, QProgressDialog
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFontMetrics, QCursor
from google import genai
from yt_dlp import YoutubeDL

vlc_args = [
	# --- 音訊輸出與音量控制 ---
	"--aout=directsound",     
	"--volume-step=1",        
	"--no-video",
	
	# --- 網路防卡死設定 (記得一定要拆開！) ---
	"--network-caching=5000", # 建議稍微加大到 5000 毫秒比較穩
	"--http-reconnect",
	
	# --- 音量自動平衡 (二選一，建議先試試方法 A) ---
	
	# 方法 A：使用 VLC 內建的簡單「音量標準化 (Volume Normalizer)」
	# 這個比 compressor 簡單粗暴，會自動把太小聲的拉大，太大聲的壓下去
	"--audio-filter=normvol",
	"--norm-max-level=2.0",   # 增強級別，數字越大提昇越多 (預設是 2.0，可以調成 3.0 或 4.0 試試)
	
	# 方法 B：如果你還是想用 Compressor，請把參數改激進一點
	# "--audio-filter=compressor",
	# "--compressor-rms-peak=0",
	# "--compressor-ratio=5.0",      # 壓縮比率調高一點
	# "--compressor-threshold=-25",  # 門檻降到 -25dB，讓小聲的音樂也能觸發壓縮器
	# "--compressor-knee=1.0",
	# "--compressor-makeup-gain=15.0" # 暴力拉高 15dB，這樣小聲的音樂就會明顯變大聲
]


CONFIG_FILE = "config.json"

class GeminiSettingsDialog(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Gemini 歌詞設定與教學")
		self.resize(500, 300) # 因為選項變少了，高度縮小一點
		self.setup_ui()
		self.load_current_config()

	def setup_ui(self):
		layout = QVBoxLayout(self)

		# --- 步驟一：教學區塊 ---
		tutorial_text = """
		<h3>步驟一：取得免費的 API Key</h3>
		<ol>
			<li>點擊前往 <a href="https://aistudio.google.com/app/apikey">Google AI Studio</a></li>
			<li>登入您的 Google 帳號</li>
			<li>點擊左上角的 <b>「Create API key」</b></li>
			<li>將產生的一長串英文數字複製下來</li>
		</ol>
		"""
		self.browser = QTextBrowser()
		self.browser.setOpenExternalLinks(True) 
		self.browser.setHtml(tutorial_text)
		self.browser.setMaximumHeight(150)
		layout.addWidget(self.browser)

		# --- 步驟二：輸入 API Key ---
		layout.addWidget(QLabel("<b>步驟二：貼上您的 API Key</b>"))
		self.key_input = QLineEdit()
		self.key_input.setPlaceholderText("請在此貼上 API Key (例如：AIzaSy...)")
		self.key_input.setEchoMode(QLineEdit.PasswordEchoOnEdit) 
		layout.addWidget(self.key_input)

		# 🌟 合併按鈕：驗證並自動儲存
		self.btn_verify_save = QPushButton("驗證 API Key 並自動設定最佳模型")
		self.btn_verify_save.clicked.connect(self.verify_and_save)
		layout.addWidget(self.btn_verify_save)

	def load_current_config(self):
		if os.path.exists(CONFIG_FILE):
			try:
				with open(CONFIG_FILE, "r", encoding="utf-8") as f:
					config = json.load(f)
					saved_key = config.get("gemini_api_key", "")
					if saved_key:
						self.key_input.setText(saved_key)
			except:
				pass

	def verify_and_save(self):
		api_key = self.key_input.text().strip()
		if not api_key:
			QMessageBox.warning(self, "錯誤", "請先輸入 API Key！")
			return

		self.btn_verify_save.setText("驗證中，尋找最佳模型...")
		self.btn_verify_save.setEnabled(False)
		
		try:
			client = genai.Client(api_key=api_key)
			available_models = []
			
			for m in client.models.list():
				supported = getattr(m, 'supported_generation_methods', [])
				if supported is None:
					supported = []
				if 'generateContent' in supported or 'gemini' in m.name.lower():
					available_models.append(m.name.replace("models/", ""))
			
			if not available_models:
				raise Exception("此 API Key 無法存取任何生成模型。")

			# 🌟 自動決策邏輯：優先找檔名有 flash 的最新模型
			flash_models = [name for name in available_models if 'flash' in name.lower()]
			best_model = flash_models[0] if flash_models else available_models[0]

			# 寫入設定檔
			config = {"gemini_api_key": api_key, "gemini_model": best_model}
			with open(CONFIG_FILE, "w", encoding="utf-8") as f:
				json.dump(config, f, indent=4)
				
			QMessageBox.information(self, "成功", f"設定完成！\n已為您自動綁定最佳模型：{best_model}")
			self.accept()
			
		except Exception as e:
			QMessageBox.critical(self, "驗證失敗", f"API Key 無效或網路錯誤：\n{e}")
		finally:
			self.btn_verify_save.setText("驗證 API Key 並自動設定最佳模型")
			self.btn_verify_save.setEnabled(True)

# --- 修改後的 Worker 部分 ---
class GeminiLyricsWorker(QThread):
	signal_done = pyqtSignal(str)
	signal_need_reset = pyqtSignal(str) 

	def __init__(self, raw_title, api_key, model_name):
		super().__init__()
		self.raw_title = raw_title
		self.api_key = api_key
		self.model_name = model_name

	def run(self):
		track_name = self.raw_title
		artist_name = ""

		# ==========================================
		# 階段一：利用 Gemini AI 萃取歌名與歌手
		# ==========================================
		try:
			client = genai.Client(api_key=self.api_key)
			
			# 強制要求輸出 JSON 格式，方便程式讀取
			prompt = (
				f"請從以下 YouTube 影片標題中，精準提取出「歌曲名稱」與「歌手名稱」。\n"
				f"影片標題：「{self.raw_title}」\n"
				"請嚴格輸出 JSON 格式，格式如下：\n"
				'{"title": "歌曲名稱", "artist": "歌手名稱"}\n'
				"如果標題中沒有歌手資訊，artist 請填寫空字串。不要輸出任何其他說明文字。"
			)

			response = client.models.generate_content(
				model=self.model_name,
				contents=prompt
			)
			
			# 清理 AI 可能帶有的 Markdown 標籤 (例如 ```json...```)
			raw_text = response.text.strip().replace('```json', '').replace('```', '')
			parsed_data = json.loads(raw_text)
			
			track_name = parsed_data.get('title', self.raw_title)
			artist_name = parsed_data.get('artist', '')
			
			print(f"🧠 AI 解析結果 -> 歌名: {track_name}, 歌手: {artist_name}")

		except Exception as e:
			error_msg = str(e).lower()
			if "quota" in error_msg or "429" in error_msg:
				self.signal_need_reset.emit("quota")
				return # 額度爆了就提早結束
			elif "not found" in error_msg or "404" in error_msg:
				self.signal_need_reset.emit("invalid_model")
				return
			else:
				print(f"Gemini 解析失敗，退回使用原始標題：{e}")
				# 解析失敗沒關係，我們用原始標題硬上


		# ==========================================
		# 階段二：向 LRCLIB 請求精準歌詞
		# ==========================================
		try:
			# 組合搜尋關鍵字
			search_query = f"{track_name} {artist_name}".strip()
			print(f"🔍 正在向 LRCLIB 搜尋: {search_query}")
			
			url = f"https://lrclib.net/api/search?q={urllib.parse.quote(search_query)}"
			
			# LRCLIB 官方要求必須附上 User-Agent，否則可能會被阻擋
			headers = {'User-Agent': 'YouTubeMusicPlayer/1.0 (https://github.com/Jenne14294)'}
			
			res = requests.get(url, headers=headers, timeout=10)
			
			if res.status_code == 200:
				data = res.json()
				if data and len(data) > 0:
					import re  # 記得在檔案最上方加上 import re (正規表示式)
					
					best_lyrics = None
					found_title = track_name
					found_artist = artist_name

					# 遍歷 LRCLIB 給的多個結果
					for track in data:
						lyrics = track.get('plainLyrics')
						if lyrics:
							# 如果是第一個有歌詞的，先當作備胎存起來
							if not best_lyrics:
								best_lyrics = lyrics
								found_title = track.get('trackName', track_name)
								found_artist = track.get('artistName', artist_name)
							
							# 🌟 探測器：檢查歌詞裡有沒有「中文字符」
							if re.search(r'[\u4e00-\u9fff]', lyrics):
								# 發現中文歌詞！立刻蓋掉備胎，然後停止搜尋
								best_lyrics = lyrics
								found_title = track.get('trackName', track_name)
								found_artist = track.get('artistName', artist_name)
								break 

					if best_lyrics:
						final_text = f"【{found_title}】 - {found_artist}\n\n{best_lyrics}"
						self.signal_done.emit(final_text)
					else:
						print("找到了歌曲，但沒有歌詞資料。")
						self.signal_done.emit("")
				else:
					print("LRCLIB 找不到這首歌。")
					self.signal_done.emit("")
			else:
				print(f"LRCLIB API 錯誤，狀態碼: {res.status_code}")
				self.signal_done.emit("")
				
		except Exception as e:
			print(f"取得 LRCLIB 歌詞發生嚴重錯誤：{e}")
			self.signal_done.emit("")

class LyricsDialog(QDialog):
	def __init__(self, title, lyrics, parent=None):
		super().__init__(parent)
		self.setWindowTitle(f"歌詞 - {title}")
		self.resize(400, 600)  # 設定視窗大小

		layout = QVBoxLayout(self)
		
		# 使用唯讀的文字框來顯示歌詞
		self.text_edit = QTextEdit(self)
		self.text_edit.setReadOnly(True)
		self.text_edit.setPlainText(lyrics)
		
		# 讓字體稍微大一點，方便閱讀
		font = self.text_edit.font()
		font.setPointSize(12)
		self.text_edit.setFont(font)
		
		layout.addWidget(self.text_edit)

class ClickableSlider(QSlider):
	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			# 計算滑鼠點擊位置在整體長度的比例
			value = QStyle.sliderValueFromPosition(
				self.minimum(), self.maximum(), event.x(), self.width()
			)
			self.setValue(value)
			self.sliderMoved.emit(value)  # 觸發移動訊號
		super().mousePressEvent(event)

class TrayIcon(QSystemTrayIcon):
	def __init__(self, icon_path, parent=None):
		super().__init__(QIcon(icon_path), parent)
		self.setToolTip("YouTube 音樂播放器 - 正在背景播放")

		self.tray_menu = QMenu()

		# 顯示資訊
		self.status_action = QAction("🎵 無播放歌曲")
		self.status_action.setEnabled(False)  # 不可點擊


		# 播放控制項目
		self.play_action = QAction("▶️ 播放")
		self.pause_action = QAction("⏯️ 暫停")
		self.prev_action = QAction("⏭️ 上一首")
		self.next_action = QAction("⏮️ 下一首")
		self.loop_action = QAction("🔁 循環播放：關")
		self.shuffle_action = QAction("🔀 隨機播放")
		self.lyrics_action = QAction("📄 查詢歌詞")


		# 音量區塊：滑桿 + 數值顯示 + 靜音按鈕
		volume_widget = QWidget()
		volume_layout = QHBoxLayout(volume_widget)
		volume_layout.setContentsMargins(8, 2, 8, 2)

		# 🔇 靜音按鈕（實體按鈕嵌入 layout）
		self.mute_button = QPushButton("🔇")
		self.mute_button.setFixedSize(24, 24)
		self.mute_button.setCheckable(True)
		self.mute_button.setToolTip("靜音 / 取消靜音")

		volume_layout.addWidget(self.mute_button)

		# 原本的音量滑桿
		self.volume_slider = QSlider(Qt.Horizontal)
		self.volume_slider.setRange(0, 100)
		self.volume_slider.setValue(70)
		self.volume_slider.setFixedWidth(100)
		self.volume_slider.setToolTip("音量調整")

		# 原本的音量數值標籤
		self.volume_label = QLabel("70")
		self.volume_label.setFixedWidth(30)

		self.volume_slider.valueChanged.connect(
			lambda val: self.volume_label.setText(str(val))
		)

		# 加入原有部件
		volume_layout.addWidget(self.volume_slider)
		volume_layout.addWidget(self.volume_label)

		# 加到托盤選單
		volume_widget_action = QWidgetAction(self.tray_menu)
		volume_widget_action.setDefaultWidget(volume_widget)


		# 其他功能
		self.restore_action = QAction("還原視窗")
		self.quit_action = QAction("結束程式")

		# 加入選單
		self.tray_menu.insertAction(self.play_action, self.status_action)  # 插入到最上方
		self.tray_menu.addAction(self.play_action)
		self.tray_menu.addAction(self.pause_action)
		self.tray_menu.addSeparator()
		self.tray_menu.addAction(self.prev_action)
		self.tray_menu.addAction(self.next_action)
		self.tray_menu.addSeparator()
		self.tray_menu.addAction(self.loop_action)
		self.tray_menu.addAction(self.shuffle_action)
		self.tray_menu.addAction(self.lyrics_action)
		self.tray_menu.addSeparator()
		self.tray_menu.addAction(volume_widget_action)  # 音量滑桿
		self.tray_menu.addSeparator()
		self.tray_menu.addAction(self.restore_action)
		self.tray_menu.addAction(self.quit_action)
		

		self.setContextMenu(self.tray_menu)

		

		# 連接訊號（假設 parent 有對應的方法）
		if parent:
			self.play_action.triggered.connect(parent.play_music)
			self.pause_action.triggered.connect(parent.toggle_pause)
			self.prev_action.triggered.connect(parent.play_prev)
			self.next_action.triggered.connect(parent.play_next)
			self.loop_action.triggered.connect(parent.toggle_loop)
			self.shuffle_action.triggered.connect(parent.toggle_shuffle)
			self.lyrics_action.triggered.connect(parent.search_lyrics)
			self.restore_action.triggered.connect(parent.showNormal)
			self.quit_action.triggered.connect(parent.quit_app)
			self.volume_slider.valueChanged.connect(parent.change_volume)
			self.mute_button.clicked.connect(parent.toggle_mute) 

		self.activated.connect(self.on_activated)

	def on_activated(self, reason):
		if reason == QSystemTrayIcon.DoubleClick and self.parent():
			self.parent().showNormal()
			self.parent().activateWindow()


	def update_status(self, title, current_time, total_time):
		self.status_action.setText(f"🎵 {title}  ⏱ {current_time}/{total_time}")

	def update_playing_state(self, is_playing: bool):
		if is_playing:
			self.pause_action.setText("⏯️ 暫停")
		else:
			self.pause_action.setText("⏯️ 繼續")

	def update_mute_state(self, is_muted: bool):
		if is_muted:
			self.mute_button.setText("🔇")
		else:
			self.mute_button.setText("🔊")

class MarqueeLabel(QLabel):
	def __init__(self, text='', parent=None):
		super().__init__(text, parent)
		self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		self.setMinimumWidth(50)
		self.offset = 0
		self.timer = QTimer(self)
		self.timer.timeout.connect(self.scrollText)
		self.fullText = text
		self.scrolling = False
		self.setText(text)

	def setText(self, text):
		self.fullText = text
		self.offset = 0
		self.timer.stop()
		self.scrolling = False

		# 立即檢查是否需要滾動
		self.checkScrolling()
		super().setText(text)

	def checkScrolling(self):
		metrics = QFontMetrics(self.font())
		text_width = metrics.width(self.fullText)

		if text_width > self.width():
			self.timer.start(300)
			self.scrolling = True
		else:
			self.timer.stop()
			self.scrolling = False
			super().setText(self.fullText)

	def scrollText(self):
		if not self.scrolling:
			return
		text = self.fullText + "     "
		self.offset = (self.offset + 1) % len(text)
		super().setText(text[self.offset:] + text[:self.offset])

	def resizeEvent(self, event):
		# 視窗改變時重新判斷是否需要滾動
		self.checkScrolling()
		super().resizeEvent(event)

class SongItemWidget(QWidget):
	def __init__(self, index, title, parent=None):
		super().__init__(parent)
		self.index = index
		self.title = title

		layout = QHBoxLayout(self)
		layout.setContentsMargins(2, 2, 2, 2)

		self.btn_up = QPushButton("⬆️")
		self.btn_up.setFixedWidth(36)

		self.btn_down = QPushButton("⬇️")
		self.btn_down.setFixedWidth(36)
		
		self.btn_delete = QPushButton("🗑️")
		self.btn_delete.setFixedWidth(36)

		self.btn_more = QPushButton("⋯")
		self.btn_more.setFixedWidth(36)

		self.label = QLabel(f"{index+1}. {title}")

		layout.addWidget(self.btn_up)
		layout.addWidget(self.btn_down)
		layout.addWidget(self.btn_delete)
		layout.addWidget(self.btn_more)
		layout.addWidget(self.label)

class SearchResultsDialog(QDialog):
	def apply_custom_theme(self):
		self.setStyleSheet("""
		QWidget {
			background-color: #1e1e2f;
			color: #ffffff;
			font-family: "Microsoft JhengHei";
			font-size: 14px;
		}
		QPushButton {
			background-color: #2e2e3f;
			border: 1px solid #555;
			border-radius: 6px;
			padding: 6px;
		}
		QPushButton:hover {
			background-color: #3e3e5f;
		}
		QPushButton:pressed {
			background-color: #5e5e7f;
		}
		QLineEdit, QListWidget {
			background-color: #2a2a3a;
			border: 1px solid #555;
			border-radius: 4px;
			padding: 4px;
		}
		QSlider::groove:horizontal {
			background: #444;
			height: 6px;
			border-radius: 3px;
		}
		QSlider::handle:horizontal {
			background: #ff8c00;
			width: 14px;
			margin: -4px 0;
			border-radius: 7px;
		}
		QListWidget::item:selected {
		background-color: #0078d7;   /* 高亮底色 */
		color: white;                /* 字體顏色 */
		font-weight: bold;           /* 粗體 */
	}
	""")
		
	def __init__(self, results, parent=None):
		super().__init__(parent)
		self.setWindowTitle("搜尋結果")
		self.resize(400, 300)
		self.apply_custom_theme()

		layout = QVBoxLayout(self)
		self.list_widget = QListWidget()
		self.list_widget.setSelectionMode(QListWidget.SingleSelection)

		# 限制只顯示前五個
		for i, item in enumerate(results):
			list_item = QListWidgetItem(f"{i + 1}. {item['title']}")
			list_item.setData(Qt.UserRole, item['url'])
			self.list_widget.addItem(list_item)

		layout.addWidget(self.list_widget)

		# 確定與取消按鈕
		button_layout = QHBoxLayout()
		btn_ok = QPushButton("加入播放清單")
		btn_cancel = QPushButton("取消")
		btn_ok.clicked.connect(self.accept)
		btn_cancel.clicked.connect(self.reject)
		button_layout.addWidget(btn_ok)
		button_layout.addWidget(btn_cancel)
		layout.addLayout(button_layout)

	def get_selected_items(self):
		"""回傳使用者選取的項目（格式：{'title':..., 'url':...}）"""
		selected = []
		for item in self.list_widget.selectedItems():
			selected.append({
				'title': item.text(),
				'url': item.data(Qt.UserRole)
			})
		return selected

class EditSongsDialog(QDialog):
	def apply_custom_theme(self):
		self.setStyleSheet("""
		QWidget {
			background-color: #1e1e2f;
			color: #ffffff;
			font-family: "Microsoft JhengHei";
			font-size: 14px;
		}
		QPushButton {
			background-color: #2e2e3f;
			border: 1px solid #555;
			border-radius: 6px;
			padding: 6px;
		}
		QPushButton:hover {
			background-color: #3e3e5f;
		}
		QPushButton:pressed {
			background-color: #5e5e7f;
		}
		QLineEdit {
			background-color: #2a2a3a;
			border: 1px solid #555;
			border-radius: 4px;
			padding: 4px;
		}
		""")

	def __init__(self, idx, parent=None):
		super().__init__(parent)
		self.setWindowTitle("編輯歌曲")
		self.resize(400, 180)
		self.apply_custom_theme()

		self.parent = parent
		self.idx = idx
		self.now_song = parent.playlist[idx] if parent else {"title": "", "url": ""}

		layout = QVBoxLayout(self)

		# 標題輸入
		hl_title = QHBoxLayout()
		hl_title.addWidget(QLabel("標題："))
		self.title_edit = QLineEdit(self.now_song.get("title", ""))
		hl_title.addWidget(self.title_edit)
		layout.addLayout(hl_title)

		# 網址輸入 + 瀏覽
		hl_url = QHBoxLayout()
		hl_url.addWidget(QLabel("網址/路徑："))
		self.url_edit = QLineEdit(self.now_song.get("url", ""))
		btn_browse = QPushButton("瀏覽")
		btn_browse.clicked.connect(self.browse_file)
		hl_url.addWidget(self.url_edit)
		hl_url.addWidget(btn_browse)
		layout.addLayout(hl_url)

		# 按鈕區
		hl_buttons = QHBoxLayout()
		btn_save = QPushButton("儲存")
		btn_cancel = QPushButton("取消")
		btn_preview = QPushButton("預覽")
		hl_buttons.addWidget(btn_save)
		hl_buttons.addWidget(btn_cancel)
		hl_buttons.addWidget(btn_preview)
		layout.addLayout(hl_buttons)

		btn_save.clicked.connect(self.save_changes)
		btn_cancel.clicked.connect(self.reject)
		btn_preview.clicked.connect(self.preview)

	def browse_file(self):
		file_path, _ = QFileDialog.getOpenFileName(
			self, "選擇音樂檔案", "",
			"音訊檔案 (*.mp3 *.wav *.m4a *.flac *.ogg *.m3u *.txt);;所有檔案 (*)"
		)
		if file_path:
			self.url_edit.setText(file_path)

	def save_changes(self):
		new_title = self.title_edit.text().strip()
		new_url = self.url_edit.text().strip()
		if self.parent:
			self.parent.playlist[self.idx]["title"] = new_title
			self.parent.playlist[self.idx]["url"] = new_url
			# 更新顯示
			self.parent.list_widget.item(self.idx).setText(new_title)
		self.accept()

	def preview(self):
		url = self.url_edit.text().strip()
		if not url:
			return
		if os.path.exists(url):
			os.startfile(url)
		else:
			webbrowser.open(url)

class PlaylistLoader(QThread):
	finished = pyqtSignal(list, bool)  # 載入完成後傳回 playlist

	def __init__(self, url, parent=None):
		super().__init__(parent)
		self.url = url
		self.is_keyword = False

	def run(self):
		playlist = []
		ydl_opts = {
			'extract_flat': True,       # 🌟 核心加速：只抓取標題和 ID，不解析真實音訊串流！
			'skip_download': True,      # 絕對不下載
			'quiet': True,              # 不輸出多餘訊息
			'ignoreerrors': True,       # 遇到無法讀取的影片(例如私人影片)直接跳過，不卡死程式
			'noplaylist': False         # 建議設為 False，這樣如果用戶輸入的是「播放清單網址」，才能秒抓整串歌單
		}

		with YoutubeDL(ydl_opts) as ydl:
			try:
				if self.url.startswith("https://"):
					info = ydl.extract_info(self.url, download=False)
				else:
					self.is_keyword = True
					search_query = f"ytsearch5:{self.url}"  # 搜尋前 5 筆
					info = ydl.extract_info(search_query, download=False)

				entries = info.get('entries', [info])
				for entry in entries:
					video_url = f"https://www.youtube.com/watch?v={entry['id']}" if 'id' in entry else entry['url']
					title = entry.get('title', video_url)
					playlist.append({'title': title, 'url': video_url})

			except Exception as e:
				print(f"讀取失敗：{e}")

		self.finished.emit(playlist, self.is_keyword)

class MusicPlayerThread(QThread):
	play_success = pyqtSignal(str, bool)  # 成功串流或下載後回傳媒體路徑（串流為 URL，下載為本地檔案）
	play_failed = pyqtSignal(str)   # 播放錯誤訊息

	def __init__(self, entry, parent=None):
		super().__init__(parent)
		self.entry = entry
		self.temp_filepath = None
		
	def run(self):
		ydl_opts = {
			'format': 'bestaudio[ext=m4a]/bestaudio/best',  # 優先 m4a
			'noplaylist': True,
			'quiet': True,
			
			# 🌟 加入這行：微調 YouTube 擷取器的客戶端設定，能繞過部分嚴格驗證
			'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
		}

		if not self.entry['url'].startswith("https://"):
			self.play_success.emit(self.entry['url'], False)

		else:
			try:
				with YoutubeDL(ydl_opts) as ydl:
					info = ydl.extract_info(self.entry['url'], download=False)
					stream_url = info['url']
					self.play_success.emit(stream_url, False)
					return
			except Exception as e:
				self.play_failed.emit(f"播放失敗：{e}")
				print("串流失敗，改為下載音訊播放")

			# try:
			# 	with YoutubeDL(ydl_opts) as ydl:
			# 		info = ydl.extract_info(self.entry['url'], download=True)
			# 		time.sleep(1)
			# 		self.temp_filepath = os.path.join(temp_dir, ydl.prepare_filename(info))
			# 		self.play_success.emit(os.path.abspath(self.temp_filepath), True)
			# except Exception as e:
			# 	self.play_failed.emit(f"播放失敗：{e}")

class DownloadThread(QThread):
	download_finished = pyqtSignal(bool, str)

	def __init__(self, url, save_path, parent=None):
		super().__init__(parent)
		self.url = url
		self.save_path = save_path

	def run(self):
		try:
			ydl_opts = {
				'format': 'bestaudio/best',
				'outtmpl': self.save_path,
				'postprocessors': [{
					'key': 'FFmpegExtractAudio',
					'preferredcodec': 'mp3',
					'preferredquality': '192',
				}],
				'quiet': True,
			}
			with YoutubeDL(ydl_opts) as ydl:
				ydl.download([self.url])
			self.download_finished.emit(True, self.save_path)
		except Exception as e:
			self.download_finished.emit(False, str(e))

class PlaylistSearchDialog(QDialog):
	def __init__(self, playlist, parent=None):
		super().__init__(parent)
		self.setWindowTitle("搜尋歌單")
		self.resize(400, 300)

		self.playlist = playlist

		layout = QVBoxLayout(self)
		self.search_input = QLineEdit()
		self.search_input.setPlaceholderText("輸入關鍵字…")
		layout.addWidget(self.search_input)

		self.list_widget = QListWidget()
		layout.addWidget(self.list_widget)

		btn_close = QPushButton("關閉")
		btn_close.clicked.connect(self.close)
		layout.addWidget(btn_close)

		self.search_input.textChanged.connect(self.update_results)
		self.list_widget.itemDoubleClicked.connect(self.select_item)

	def update_results(self, keyword):
		self.list_widget.clear()
		keyword = keyword.lower()
		for idx, song in enumerate(self.playlist):
			if keyword in song['title'].lower():
				item = QListWidgetItem(f"{idx+1}. {song['title']}")
				item.setData(1, idx)  # 存下 index
				self.list_widget.addItem(item)

	def select_item(self, item):
		idx = item.data(1)
		self.accept()
		self.selected_index = idx

	def get_selected_index(self):
		return getattr(self, 'selected_index', None)

class ExportPlaylistDialog(QDialog):
	def __init__(self, playlist, parent=None):
		super().__init__(parent)
		self.playlist = playlist
		self.save_playlist()

	def save_playlist(self):
		# 出現「另存為」對話框
		path, _ = QFileDialog.getSaveFileName(
			self,
			"匯出播放清單",
			"playlist.m3u",
			"M3U 檔案 (*.m3u)"
		)

		if not path:
			return  # 使用者取消

		# 確保副檔名
		if not path.lower().endswith(".m3u"):
			path += ".m3u"

		try:
			with open(path, "w", encoding="utf-8") as f:
				f.write("#EXTM3U\n")
				for item in self.playlist:
					f.write(f"#EXTINF:-1,{item['title']}\n")
					f.write(f"{item['url']}\n")

			QMessageBox.information(self, "匯出成功", f"播放清單已儲存到：\n{path}")
		except Exception as e:
			QMessageBox.critical(self, "匯出失敗", f"無法儲存播放清單：\n{e}")

class VlcStatusWorker(QThread):
	# 定義信號：分別傳送 (當前時間, 總長度, 狀態)
	# 使用 int, int, object (因為 state 是 vlc 的物件)
	status_updated = pyqtSignal(int, int, object)

	def __init__(self, player):
		super().__init__()
		self.player = player
		self.is_running = True

	def run(self):
		while self.is_running:
			if self.player:
				try:
					# 這些是有可能卡住的網路操作，現在在背景跑
					current = self.player.get_time()
					length = self.player.get_length()
					state = self.player.get_state()
					
					# 發射信號回主線程 (這不會卡住)
					self.status_updated.emit(current, length, state)
				except Exception as e:
					print(f"VLC Worker Error: {e}")
			
			# 不需要太快，0.2 ~ 0.5 秒一次即可
			time.sleep(0.2)

	def stop(self):
		self.is_running = False
		self.wait()

class YouTubePlayer(QWidget):
	def apply_custom_theme(self):
		self.setStyleSheet("""
		QWidget {
			background-color: #1e1e2f;
			color: #ffffff;
			font-family: "Microsoft JhengHei";
			font-size: 14px;
		}
		QPushButton {
			background-color: #2e2e3f;
			border: 1px solid #555;
			border-radius: 6px;
			padding: 6px;
		}
		QPushButton:hover {
			background-color: #3e3e5f;
		}
		QPushButton:pressed {
			background-color: #5e5e7f;
		}
		QLineEdit, QListWidget {
			background-color: #2a2a3a;
			border: 1px solid #555;
			border-radius: 4px;
			padding: 4px;
		}
		QSlider::groove:horizontal {
			background: #444;
			height: 6px;
			border-radius: 3px;
		}
		QSlider::handle:horizontal {
			background: #ff8c00;
			width: 14px;
			margin: -4px 0;
			border-radius: 7px;
		}
		QListWidget::item:selected {
		background-color: #0078d7;   /* 高亮底色 */
		color: white;                /* 字體顏色 */
		font-weight: bold;           /* 粗體 */
	}
	""")


	def __init__(self):
		super().__init__()
		self.setWindowTitle("YouTube 音樂播放器")
		self.setGeometry(300, 200, 500, 550)
		icon_path = "icon.ico"
		self.setWindowIcon(QIcon(icon_path))

		self.tray_icon = TrayIcon(icon_path, self)
		self.tray_icon.show()

		self.playlist = []
		self.current_index = 0
		self.playlist_length = 0
		self.loop = False
		self.instance = vlc.Instance(vlc_args)
		self.player = self.instance.media_player_new()
		self.temp_filepath = None
		self.seeking = False
		self.is_handling_end = False

		self.init_ui()
		self.apply_custom_theme()

		# 不再使用 QTimer 來呼叫 update_status
		self.status_worker = VlcStatusWorker(self.player)
		# 將信號連接到你的更新函式
		self.status_worker.status_updated.connect(self.update_status)
		# 開始執行緒
		self.status_worker.start()


	def init_ui(self):
		layout = QGridLayout()

		# 建立一個橫向容器來放 QLineEdit 和瀏覽按鈕
		input_layout = QHBoxLayout()

		# 原本的網址輸入欄位
		self.url_input = QLineEdit()
		self.url_input.setPlaceholderText("輸入 YouTube 網址或播放清單網址")
		input_layout.addWidget(self.url_input)

		# 新增「瀏覽」按鈕
		self.browse_button = QPushButton("📂 瀏覽")
		self.browse_button.clicked.connect(self.browse_local_file)
		input_layout.addWidget(self.browse_button)

		# 把整個橫向區塊加到主 layout 上（佔一列）
		layout.addLayout(input_layout, 0, 0)  # ⬅️ 第 0 行、橫跨三欄


		# 第一列按鈕
		self.load_button = QPushButton("🔍 搜尋")
		self.load_button.clicked.connect(self.load_playlist)
		layout.addWidget(self.load_button, 0, 1)

		self.play_button = QPushButton("▶️ 播放")
		self.play_button.clicked.connect(self.play_music)
		layout.addWidget(self.play_button, 0, 2)

		self.pause_button = QPushButton("⏯️ 暫停")
		self.pause_button.clicked.connect(self.toggle_pause)
		layout.addWidget(self.pause_button, 1, 0)

		# 第二列按鈕
		self.prev_button = QPushButton("⏮️ 上一首")
		self.prev_button.clicked.connect(self.play_prev)
		layout.addWidget(self.prev_button, 1, 1)

		self.next_button = QPushButton("⏭️ 下一首")
		self.next_button.clicked.connect(self.play_next)
		layout.addWidget(self.next_button, 1, 2)


		# 第三列按鈕
		self.loop_button = QPushButton("🔁 循環播放：🟥")
		self.loop_button.clicked.connect(self.toggle_loop)
		layout.addWidget(self.loop_button, 2, 0)

		self.shuffle_button = QPushButton("🔀 隨機播放")
		self.shuffle_button.clicked.connect(self.toggle_shuffle)
		layout.addWidget(self.shuffle_button, 2, 1)  # 中間放置

		self.lyrics_button = QPushButton("📄 查詢歌詞")
		self.lyrics_button.clicked.connect(self.search_lyrics)
		layout.addWidget(self.lyrics_button, 2, 2)


		# 音量控制
		self.volume_label = QLabel("音量：70")
		layout.addWidget(self.volume_label, 3, 0)

		self.volume_slider = ClickableSlider(Qt.Horizontal)
		self.volume_slider.setRange(0, 100)
		self.volume_slider.setValue(70)
		self.player.audio_set_volume(70)
		self.volume_slider.valueChanged.connect(self.change_volume)
		layout.addWidget(self.volume_slider, 3, 1)

		self.mute_button = QPushButton("🔇 靜音")
		self.mute_button.setCheckable(True)
		self.mute_button.clicked.connect(self.toggle_mute)
		layout.addWidget(self.mute_button, 3, 2)


		# 時間控制
		self.time_label = QLabel("播放時間：00:00 / 00:00")
		layout.addWidget(self.time_label, 4, 0)

		self.position_slider = ClickableSlider(Qt.Horizontal)
		self.position_slider.setRange(0, 1000)
		self.position_slider.sliderMoved.connect(self.seek_position)
		layout.addWidget(self.position_slider, 4, 1, 1, 2)


		# 歌名顯示
		self.current_label = QLabel("正在播放：")
		self.current_title = MarqueeLabel(" ")
		layout.addWidget(self.current_label, 5, 0)
		layout.addWidget(self.current_title, 5, 1, 1, 2)

		# 歌曲總數顯示
		playlist_layout = QHBoxLayout()

		self.current_length = QLabel(f"歌曲數量：0 / 0")
		playlist_layout.addWidget(self.current_length)

		self.search_playlist = QPushButton("🔍 查詢歌單")
		self.search_playlist.clicked.connect(self.search_in_playlist)
		playlist_layout.addWidget(self.search_playlist)

		layout.addLayout(playlist_layout, 6, 0)  # 放在第六行，橫跨三欄
		

		self.export_playlist = QPushButton("📤 匯出歌單")
		self.export_playlist.clicked.connect(self.export_playlist_to_file)
		layout.addWidget(self.export_playlist, 6, 1)

		self.clear_button = QPushButton("⏏️ 清除歌單")
		self.clear_button.clicked.connect(self.clear_playlist)
		layout.addWidget(self.clear_button, 6, 2)

		# 歌單顯示
		self.list_widget = QListWidget()
		self.list_widget.itemDoubleClicked.connect(lambda _: self.select_song())
		layout.addWidget(self.list_widget, 7, 0, 1, 3)  # 橫跨兩欄

		self.setLayout(layout)


	def load_playlist(self):
		url = self.url_input.text()

		print(url)

		if not url:
			return
			
		# 啟動背景載入執行緒
		self.loader_thread = PlaylistLoader(url)
		self.loader_thread.finished.connect(self.on_playlist_loaded)
		self.loader_thread.start()

	def load_playlist_from_file(self, file_list):
		for file_path in file_list:
			if file_path.endswith('.m3u'):
				playlist = []
				with open(file_path, 'r', encoding='utf-8') as f:
					lines = [line.strip() for line in f if line.strip() and not line.startswith("#EXTM3U")]

				i = 0
				while i < len(lines):
					if lines[i].startswith("#EXTINF:"):
						title = lines[i].split(",", 1)[1] if "," in lines[i] else "未知標題"
						i += 1
						if i < len(lines):
							url = lines[i]
							playlist.append({'title': title, 'url': url})
					i += 1
			else:
				# 單純本地檔案
				title = os.path.basename(file_path)
				playlist = [{'title': title, 'url': file_path}]

			# 將讀到的這個檔案的歌曲加入播放清單並顯示
			for song in playlist:
				self.playlist.append(song)

		
		self.refresh_playlist_ui()  # 刷新 UI 顯示	
		self.update_playlist_status()  # 更新歌曲數量顯示


	def on_playlist_loaded(self, playlist, is_keyword):
		if is_keyword:
			dialog = SearchResultsDialog(playlist)  # search_results 是 [{'title':..., 'url':...}, ...]
			if dialog.exec_() == QDialog.Accepted:
				selected = dialog.get_selected_items()
				for item in selected:
					self.playlist.append(item)

		else:
			self.playlist.extend(playlist)
			
		self.refresh_playlist_ui()

	def clear_playlist(self):
		self.player.stop()  # 停止當前播放（如有）
		self.cleanup_temp_file()  # 清除暫存音訊（如果你有實作）

		self.playlist.clear()  # 清除內部播放清單
		self.list_widget.clear()  # 清空顯示列表
		self.current_index = 0
		self.current_title.setText(" ")
		self.update_playlist_status()  # 更新歌曲數量顯示

	def update_playlist_status(self):
		self.playlist_length = len(self.playlist)
		self.current_length.setText(f"歌曲數量：{self.current_index + 1 % self.playlist_length if self.playlist_length > 0 else 0} / {self.playlist_length}")

	def move_song_up(self, idx):
		if idx > 0:
			self.playlist[idx-1], self.playlist[idx] = self.playlist[idx], self.playlist[idx-1]
			self.refresh_playlist_ui(select_idx=idx-1)  # 移動後保持顯示

	def move_song_down(self, idx):
		if idx < len(self.playlist) - 1:
			self.playlist[idx+1], self.playlist[idx] = self.playlist[idx], self.playlist[idx+1]
			self.refresh_playlist_ui(select_idx=idx+1)

	def swap_songs(self, operator_idx, operation_idx):
		temp_song = self.playlist[operation_idx]
		self.playlist[operation_idx] = self.playlist[operator_idx]
		self.playlist[operator_idx] = temp_song

		self.refresh_playlist_ui()
	
	def delete_song(self, idx):
		self.playlist.pop(idx)
		self.refresh_playlist_ui()

	def more_options(self, idx):
		"""更多選項（如刪除、上移、下移）"""
		menu = QMenu(self)

		edit_action = QAction("📝 編輯")
		edit_action.triggered.connect(lambda: self.edit_select_song(idx))
		menu.addAction(edit_action)

		download_action = QAction("⬇️ 下載")
		download_action.triggered.connect(lambda: self.download_select_song(idx))
		menu.addAction(download_action)

		sshare_song_action = QAction("📄 歌詞")
		sshare_song_action.triggered.connect(lambda: self.search_lyrics(idx))
		menu.addAction(sshare_song_action)

		share_song_action = QAction("ℹ️ 分享")
		share_song_action.triggered.connect(lambda: self.copy_selected_song_url(idx))
		menu.addAction(share_song_action)

		menu.exec_(QCursor.pos())

	def refresh_playlist_ui(self, select_idx=None):
		"""清空並重新生成歌單 UI"""
		self.list_widget.clear()

		for i, song in enumerate(self.playlist):
			item = QListWidgetItem()
			widget = SongItemWidget(i, song['title'])

			# 綁定按鈕事件
			widget.btn_up.clicked.connect(lambda _, idx=i: self.move_song_up(idx))
			widget.btn_down.clicked.connect(lambda _, idx=i: self.move_song_down(idx))
			widget.btn_delete.clicked.connect(lambda _, idx=i: self.delete_song(idx))
			widget.btn_more.clicked.connect(lambda _, idx=i: self.more_options(idx))

			item.setSizeHint(widget.sizeHint())
			self.list_widget.addItem(item)
			self.list_widget.setItemWidget(item, widget)

		self.update_playlist_status()

		# ✅ 保持顯示指定歌曲
		if select_idx is not None and 0 <= select_idx < self.list_widget.count():
			self.list_widget.setCurrentRow(select_idx)
			item = self.list_widget.item(select_idx)
			self.list_widget.scrollToItem(item)   # <-- 自動捲到指定歌曲

	def edit_select_song(self, idx):
		dialog = EditSongsDialog(idx, self)
		dialog.exec_()

	def download_select_song(self, idx):
		url = self.playlist[idx]['url']
		title = self.playlist[idx]['title']

		if not url.startswith("http"):
			QMessageBox.warning(self, "無效的網址", "請選擇有效的 YouTube 網址或播放清單。")
			return

		# 先讓使用者選儲存路徑
		save_path, _ = QFileDialog.getSaveFileName(
			self,
			"選擇儲存位置",
			f"{title}.mp3",
			"音訊檔案 (*.mp3)"
		)
		if not save_path:
			return  # 使用者取消

		# 啟動下載執行緒
		self.download_thread = DownloadThread(url, save_path)
		self.download_thread.download_finished.connect(self.on_download_finished)
		self.download_thread.start()


	def on_download_finished(self, success, message):
		if success:
			QMessageBox.information(self, "下載完成", f"音樂已儲存到：\n{message}")
		else:
			QMessageBox.warning(self, "下載失敗", f"發生錯誤：\n{message}")


	def copy_selected_song_url(self, idx):
		song = self.playlist[idx]
		QApplication.clipboard().setText(f"透過 Youtube 音樂播放器分享這首歌給你：{song['title']}\n網址：{song['url']}")

		self.tray_icon.showMessage(
			"YouTube 音樂播放器",
			"已將該歌曲複製到剪貼簿！",
			QSystemTrayIcon.Information,
			3000
		)

	def play_music(self):
		if not self.playlist:
			return

		self.player.stop()
		self.cleanup_temp_file()

		entry = self.playlist[self.current_index]
		self.current_title.setText(f"{entry['title']}")
		self.list_widget.setCurrentRow(self.current_index)
		self.temp_filepath = None

		# 啟動播放用的 QThread
		self.music_thread = MusicPlayerThread(entry)
		self.music_thread.play_success.connect(self.handle_play_success)
		self.music_thread.play_failed.connect(self.handle_play_failed)
		self.music_thread.start()

		self.update_playlist_status()  # 更新播放清單顯示

	def handle_play_success(self, media_path, is_downloaded=False):
		# 串流（http）或本地檔案都可以用 media_new
		if not os.path.exists(media_path):
			if not media_path.startswith("http"):
				QMessageBox.critical(self, "錯誤", f"無法播放 {media_path}，\n請確認網址或檔案路徑是否正確。")
				return

		# 這裡加上 self. ，讓它變成實例變數，常駐在記憶體中！
		self.current_media = self.instance.media_new(media_path)
		self.player.set_media(self.current_media)
		self.player.play()
		
		# 如果是下載的檔案，記得保存 temp 檔路徑以便清理
		if not media_path.startswith("http") and is_downloaded:
			self.temp_filepath = media_path

	def handle_play_failed(self, msg):
		QMessageBox.critical(self, "錯誤", f"無法播放\n{msg}")
		# 你也可以彈出 QMessageBox 或更新 UI 顯示錯誤



	def cleanup_temp_file(self):
		if self.temp_filepath and os.path.exists(self.temp_filepath):
			try:
				os.remove(self.temp_filepath)
				print(f"已刪除暫存檔：{self.temp_filepath}")
			except Exception as e:
				print(f"刪除檔案失敗：{e}")
		self.temp_filepath = None


	def toggle_pause(self):
		if self.player.is_playing():
			self.player.pause()
			self.tray_icon.update_playing_state(False)  # 暫停時
			self.pause_button.setText("⏯️ 繼續")
		else:
			self.player.play()
			self.tray_icon.update_playing_state(True)   # 開始播放時
			self.pause_button.setText("⏯️ 暫停")


	def play_next(self):
		self.is_handling_end = True  # 主動切歌時也設為 True
		self.cleanup_temp_file()

		if not self.playlist:
			return
		
		self.current_index = (self.current_index + 1) % len(self.playlist)
		self.play_music()
		QTimer.singleShot(1500, self.reset_end_flag)

	def play_prev(self):
		self.cleanup_temp_file()
		if not self.playlist:
			return
		self.current_index = (self.current_index - 1 + len(self.playlist)) % len(self.playlist)
		self.play_music()

	

	def toggle_loop(self):
		self.loop = not self.loop
		status = "🟢" if self.loop else "🟥"
		self.loop_button.setText(f"🔁 循環播放：{status}")
		self.tray_icon.loop_action.setText(f"🔁 循環播放：{status}")

	def toggle_shuffle(self):
		random.shuffle(self.playlist)
		self.refresh_playlist_ui()

	

	def open_gemini_settings(self):
		"""隨時呼叫這個函式，就可以打開設定視窗讓用戶換模型"""
		dialog = GeminiSettingsDialog(self)
		dialog.exec_()

	def get_gemini_config(self):
		"""讀取目前的設定"""
		if os.path.exists(CONFIG_FILE):
			try:
				with open(CONFIG_FILE, "r", encoding="utf-8") as f:
					return json.load(f)
			except:
				pass
		return {}

	def load_api_key(self):
		"""讀取設定檔中的 API Key"""
		if os.path.exists(CONFIG_FILE):
			try:
				with open(CONFIG_FILE, "r", encoding="utf-8") as f:
					config = json.load(f)
					return config.get("gemini_api_key", "")
			except Exception as e:
				print("讀取設定檔失敗:", e)
		return ""

	def save_api_key(self, api_key):
		"""將 API Key 存入設定檔"""
		config = {}
		if os.path.exists(CONFIG_FILE):
			try:
				with open(CONFIG_FILE, "r", encoding="utf-8") as f:
					config = json.load(f)
			except:
				pass
		
		config["gemini_api_key"] = api_key
		
		with open(CONFIG_FILE, "w", encoding="utf-8") as f:
			json.dump(config, f, indent=4)

	def search_lyrics(self, selected_index=None):
		# 讀取設定檔
		config = self.get_gemini_config()
		api_key = config.get("gemini_api_key", "")
		model_name = config.get("gemini_model", "")

		# 防呆
		if not api_key or not model_name:
			self.tray_icon.showMessage("提示", "請先設定 Gemini API 與模型", 1, 3000)
			self.open_gemini_settings()
			return

		if not self.playlist:
			return

		selected_index = self.current_index if not selected_index else selected_index
		
		# 🌟 取得完整的影片標題
		self.current_lyrics_title = self.playlist[selected_index]["title"]

		# 🌟 顯示載入中彈出視窗
		self.loading_dialog = QProgressDialog("正在從 Gemini 查詢完整歌詞...", None, 0, 0, self)
		self.loading_dialog.setWindowTitle("請稍候")
		self.loading_dialog.setWindowModality(Qt.WindowModal)
		self.loading_dialog.setCancelButton(None) # 隱藏取消按鈕避免意外報錯
		self.loading_dialog.show()

		# 🌟 啟動 Worker (精準傳遞 3 個參數)
		self.lyrics_worker = GeminiLyricsWorker(self.current_lyrics_title, api_key, model_name)
		self.lyrics_worker.signal_done.connect(self.on_lyrics_found)
		self.lyrics_worker.signal_need_reset.connect(self.handle_gemini_error) # 對應你原本的錯誤處理
		self.lyrics_worker.start()

	def on_lyrics_found(self, lyrics):
		# 關閉載入中視窗
		if hasattr(self, 'loading_dialog'):
			self.loading_dialog.close()
			
		if lyrics:
			# 🌟 關鍵修改：用 self.lyrics_window 存起來，並用 show() 顯示
			self.lyrics_window = LyricsDialog(self.current_lyrics_title, lyrics, self)
			# 確保視窗不會鎖死主程式 (設定為非獨佔模式)
			self.lyrics_window.setWindowModality(Qt.NonModal) 
			self.lyrics_window.show()
		else:
			QMessageBox.information(self, "搜不到", "抱歉，AI 找不到這首歌的完整歌詞。")

	def show_lyrics(self, lyrics_text):
		if lyrics_text:
			# 搜尋成功，打開我們自訂的歌詞視窗
			self.lyrics_window = LyricsDialog(self.current_lyrics_title, lyrics_text, self)
			self.lyrics_window.show()
		else:
			# 搜尋失敗 (可能是 Key 錯誤、額度用盡或網路問題)
			self.tray_icon.showMessage(
				"歌詞搜尋失敗",
				"找不到歌詞，或 API Key 無效/網路異常",
				2, # QSystemTrayIcon.Warning
				3000
			)
			
			# 如果懷疑是 Key 的問題，可以給個重設的選項 (非必要，可選加)
			reply = QMessageBox.question(
				self, '搜尋失敗', '無法取得歌詞。是否要重新設定 API Key？',
				QMessageBox.Yes | QMessageBox.No, QMessageBox.No
			)
			if reply == QMessageBox.Yes:
				self.save_api_key("") # 清空 Key
				self.search_lyrics()  # 重新觸發搜尋流程

	def handle_gemini_error(self, error_type):
		"""當模型失效或額度爆掉時觸發"""
		if error_type == "quota":
			msg = "您的 API 免費額度似乎已經用盡了！\n請更換一個 Google 帳號申請新的 API Key。"
		elif error_type == "invalid_model":
			msg = "您目前選擇的 AI 模型已失效或被移除！\n請重新驗證並選擇其他模型。"
		else:
			msg = "發生未知錯誤，請檢查網路或 API 狀態。"
			
		QMessageBox.critical(self, "Gemini API 異常", msg)
		# 強制開啟設定視窗讓用戶重選
		self.open_gemini_settings()

	def search_in_playlist(self):
		dialog = PlaylistSearchDialog(self.playlist, self)
		if dialog.exec_() == QDialog.Accepted:
			idx = dialog.get_selected_index()
			if idx is not None:
				self.select_song(idx)  # 你自己的「播放第 i 首歌」的方法

	def export_playlist_to_file(self):
		if not self.playlist:
			QMessageBox.warning(self, "沒有歌曲", "播放清單是空的，無法匯出。")
			return

		ExportPlaylistDialog(self.playlist, self)

	def browse_local_file(self):
		file_path, _ = QFileDialog.getOpenFileNames(
			self,
			"選擇音樂或播放清單檔案",
			"",
			"所有支援檔案 (*.mp3 *.wav *.m4a *.flac *.ogg *.m3u *.txt);;"
			"音訊檔案 (*.mp3 *.wav *.m4a *.flac *.ogg);;"
			"播放清單 (*.m3u *.txt)"
		)
		if file_path:
			self.load_playlist_from_file(file_path)

	def change_volume(self, value):
		self.player.audio_set_volume(value)
		self.volume_label.setText(f"音量：{value}")

	def toggle_mute(self):
		muted = self.player.audio_get_mute()
		self.mute_button.setText("🔊 取消靜音" if not muted else "🔇 靜音")
		self.tray_icon.update_mute_state(not muted)
		self.player.audio_toggle_mute()


	def select_song(self, idx=None):
		row = self.list_widget.currentRow() if not idx else idx
		
		if row != -1:
			self.current_index = row
			self.pause_button.setText("⏯️ 暫停")
			self.play_music()
			self.update_playlist_status()  # 更新歌曲數量顯示

	def seek_position(self, position):
		if self.player.get_length() > 0:
			new_time = int(position / 1000 * self.player.get_length())
			self.seeking = True
			self.player.set_time(new_time)
			QTimer.singleShot(500, lambda: setattr(self, 'seeking', False))

	def update_status(self, current, length, state):
		if not self.playlist:
			return 
		
		# 這裡不需要再寫 self.player.get_state() 了，直接用傳進來的 state
		
		entry = self.playlist[self.current_index]
		title = entry['title']

		# 限制觸發 Ended 的冷卻期 + 單次處理
		if state == vlc.State.Ended and not self.is_handling_end:
			self.is_handling_end = True
			self.end_handled_time = time.time()
			self.cleanup_temp_file()
			if self.loop:
				self.play_music()
			else:
				self.play_next()
			QTimer.singleShot(1500, self.reset_end_flag)

		if not self.seeking:
			# 這裡也不用 self.player.get_time() 了，直接用傳進來的 current, length
			if length > 0:
				ratio = current / length
				self.position_slider.setValue(int(ratio * 1000))

			total_time = f"{length // 60000:02}:{(length // 1000) % 60:02}" if length > 0 else "00:00"
			
			# 防止剛開始 current 為 -1
			safe_current = current if current >= 0 else 0
			current_time = f"{safe_current // 60000:02}:{(safe_current // 1000) % 60:02}"
			
			self.time_label.setText(f"播放時間：{current_time} / {total_time}")
			self.tray_icon.update_status(title, current_time, total_time)



	def reset_end_flag(self):
		# 只有在 VLC 狀態為 Playing、Paused 等有效狀態才解鎖
		if self.player.get_state() not in [vlc.State.Ended, vlc.State.Error]:
			self.is_handling_end = False
		else:
			QTimer.singleShot(500, self.reset_end_flag)

	def closeEvent(self, event):
		reply = QMessageBox.question(
			self,
			"關閉程式確認",
			"您確定要關閉程式嗎？",
			QMessageBox.Yes | QMessageBox.No,
			QMessageBox.Yes
		)

		if reply == QMessageBox.No:
			event.ignore()  # 忽略關閉，隱藏視窗
			self.hide()
			self.tray_icon.showMessage(
				"YouTube 音樂播放器",
				"程式已隱藏至通知列。",
				QSystemTrayIcon.Information,
				3000
			)
		else:
			self.quit_app()


	def on_tray_icon_activated(self, reason):
			"""點擊托盤圖示的回調"""
			if reason == QSystemTrayIcon.DoubleClick:
				self.showNormal()
				self.activateWindow()  # 將視窗帶到前景

	def quit_app(self):
			"""結束程式，清理資源"""
			self.tray_icon.hide()
			self.status_worker.stop()
			QApplication.quit()


if __name__ == "__main__":
	app = QApplication(sys.argv)
	window = YouTubePlayer()
	window.show()
	sys.exit(app.exec_())
