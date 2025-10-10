import sys
import random
import time
import os
import vlc
import google.generativeai as gemini #gemini api
import requests
import webbrowser

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QListWidget, QLabel, QSlider, QStyle, QGridLayout, QSystemTrayIcon, QMenu, QAction, QWidgetAction, QHBoxLayout, QMessageBox, QDialog, QVBoxLayout, QListWidgetItem, QFileDialog, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFontMetrics, QCursor
from yt_dlp import YoutubeDL

vlc_args = [
    "--audio-replay-gain-mode=track",
    "--audio-filter=compressor",
    "--compressor-rms-peak=0",
    "--compressor-ratio=4.0",
    "--compressor-threshold=-10",
    "--compressor-knee=1.0",
    "--compressor-makeup-gain=5.0",
	"--aout=directsound",     # 或 "--aout=wasapi"
    "--volume-step=1",         # 音量控制最小單位
]


class AI_title():
	api_key = "AIzaSyD1-M3YfupWpHFTG6GfYlwD0A9CWEURXPc"
	gemini.configure(api_key = api_key)
	model = gemini.GenerativeModel('gemini-2.0-flash')

	chat = model.start_chat(history=[])

	def ask_ai(self, content):
		response = self.chat.send_message(
			content, 
			generation_config = gemini.types.GenerationConfig(
				candidate_count = 1,
				max_output_tokens = 2000,
				temperature=0.2
				)
			)
		
		return response.text

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
			'quiet': True,
			'extract_flat': 'in_playlist',
			'force_generic_extractor': True,
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
			'quiet': True
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

class LyricsWorker(QThread):
	signal_done = pyqtSignal(str)  # 發送歌詞網址或 None

	def __init__(self, title):
		super().__init__()
		self.title = title

	def run(self):
		try:
			client_access_token = "aW0PCZtUaF6ol8tBEFw6iAQ0dYakXRLpb_1nYzoOJBnAIbzctmdBK7c3IvcvE5Hs"
			url = f"http://api.genius.com/search?q={self.title}&access_token={client_access_token}"
			response = requests.get(url)
			json_data = response.json()
			song = json_data['response']['hits'][0]['result']['relationships_index_url']
			self.signal_done.emit(song)
		except Exception as e:
			print("歌詞搜尋錯誤：", e)
			self.signal_done.emit(None)

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
		self.timer = QTimer()
		self.timer.timeout.connect(self.update_status)
		self.timer.start(1000)
		self.apply_custom_theme()


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

		media = self.instance.media_new(media_path)
		self.player.set_media(media)
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

	def search_lyrics(self, selected_index=None):
		self.tray_icon.showMessage(
			"YouTube 音樂播放器",
			"正在搜尋歌詞，找到會自動開啟網頁(可能會找到錯誤的歌曲)",
			QSystemTrayIcon.Information,
			3000
		)

		selected_index = self.current_index if not selected_index else selected_index

		current_song = self.playlist[selected_index]["title"]
		ai_title = AI_title()
		true_title = ai_title.ask_ai(f"請給我這首歌的歌名 只要歌名就好\n{current_song}")

		self.lyrics_thread = LyricsWorker(true_title)
		self.lyrics_thread.signal_done.connect(self.open_lyrics)
		self.lyrics_thread.start()


	def open_lyrics(self, url):
		if url:
			webbrowser.get('windows-default').open_new(url)
		else:
			self.tray_icon.showMessage(
				"歌詞搜尋失敗",
				"找不到歌詞或搜尋錯誤",
				QSystemTrayIcon.Warning,
				3000
			)

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
			self.play_music()
			self.update_playlist_status()  # 更新歌曲數量顯示

	def seek_position(self, position):
		if self.player.get_length() > 0:
			new_time = int(position / 1000 * self.player.get_length())
			self.seeking = True
			self.player.set_time(new_time)
			QTimer.singleShot(500, lambda: setattr(self, 'seeking', False))

	def update_status(self):
		if not self.playlist:
			return 
		
		entry = self.playlist[self.current_index]
		title = entry['title']

		state = self.player.get_state()
		
		# 限制觸發 Ended 的冷卻期 + 單次處理
		if state == vlc.State.Ended and not self.is_handling_end:
			self.is_handling_end = True
			self.end_handled_time = time.time()  # 加上處理時間紀錄
			self.cleanup_temp_file()
			if self.loop:
				self.play_music()
			else:
				self.play_next()
			QTimer.singleShot(1500, self.reset_end_flag)  # 延長到 1.5 秒

		if not self.seeking:
			length = self.player.get_length()
			current = self.player.get_time()
			if length > 0:
				ratio = current / length
				self.position_slider.setValue(int(ratio * 1000))

			total_time = f"{length // 60000:02}:{(length // 1000) % 60:02}" if length > 0 else "00:00"
			current_time = f"{current // 60000:02}:{(current // 1000) % 60:02}" if current >= 0 else "00:00"
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
			QApplication.quit()


if __name__ == "__main__":
	app = QApplication(sys.argv)
	window = YouTubePlayer()
	window.show()
	sys.exit(app.exec_())
