import sys
import random
import threading
import time
import os
import vlc
import google.generativeai as gemini #gemini api
import requests
import webbrowser

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QListWidget, QLabel, QSlider, QStyle, QGridLayout, QSystemTrayIcon, QMenu, QAction, QWidgetAction, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFontMetrics
from yt_dlp import YoutubeDL


class AI_title():
	api_key = "AIzaSyDPmuDwgNK9sp3DiYyW9f6cvSoZwu5SfDE"
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


		# 音量區塊：滑桿 + 數值顯示
		volume_widget = QWidget()
		volume_layout = QHBoxLayout(volume_widget)
		volume_layout.setContentsMargins(8, 2, 8, 2)

		self.volume_slider = QSlider(Qt.Horizontal)
		self.volume_slider.setRange(0, 100)
		self.volume_slider.setValue(50)
		self.volume_slider.setFixedWidth(100)
		self.volume_slider.setToolTip("音量調整")

		self.volume_label = QLabel("50")
		self.volume_label.setFixedWidth(30)

		self.volume_slider.valueChanged.connect(
			lambda val: self.volume_label.setText(str(val))
		)

		volume_layout.addWidget(self.volume_slider)
		volume_layout.addWidget(self.volume_label)

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

		self.activated.connect(self.on_activated)

	def on_activated(self, reason):
		if reason == QSystemTrayIcon.DoubleClick and self.parent():
			self.parent().showNormal()
			self.parent().activateWindow()


	def update_status(self, title, current_time, total_time):
		self.status_action.setText(f"🎵 {title}  ⏱ {current_time}/{total_time}")

class MarqueeLabel(QLabel):
	def __init__(self, text='', parent=None):
		super().__init__(text, parent)
		self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
		self.offset = 0
		self.timer = QTimer(self)
		self.timer.timeout.connect(self.scrollText)
		self.setFixedWidth(300)
		self.fullText = text
		self.scrolling = False
		self.setText(text)

	def setText(self, text):
		self.fullText = text
		metrics = QFontMetrics(self.font())
		text_width = metrics.width(text)

		self.offset = 0
		self.timer.stop()
		self.scrolling = False

		if text_width > self.width():
			self.timer.start(300)  # 啟動滾動
			self.scrolling = True
		super().setText(text)

	def scrollText(self):
		if not self.scrolling:
			return
		text = self.fullText
		self.offset = (self.offset + 1) % len(text)
		super().setText(text[self.offset:] + text[:self.offset])



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
		self.loop = False
		self.instance = vlc.Instance('--network-caching=1000', '--file-caching=1000', '--live-caching=1000')
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

		self.url_input = QLineEdit()
		self.url_input.setPlaceholderText("輸入 YouTube 網址或播放清單網址")
		layout.addWidget(self.url_input, 0, 0)  # 橫跨三欄

		# 第一列按鈕
		self.load_button = QPushButton("載入播放清單")
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


		# 第三列按鈕（可加其他功能）
		self.loop_button = QPushButton("🔁 循環播放：🟥")
		self.loop_button.clicked.connect(self.toggle_loop)
		layout.addWidget(self.loop_button, 2, 0)

		self.shuffle_button = QPushButton("🔀 隨機播放")
		self.shuffle_button.clicked.connect(self.toggle_shuffle)
		layout.addWidget(self.shuffle_button, 2, 1)  # 中間放置

		self.lyrics_button = QPushButton("📄 查詢歌詞")
		self.lyrics_button.clicked.connect(self.search_lyrics)
		layout.addWidget(self.lyrics_button, 2, 2)

		self.volume_label = QLabel("音量：70")
		layout.addWidget(self.volume_label, 3, 0)

		self.volume_slider = ClickableSlider(Qt.Horizontal)
		self.volume_slider.setRange(0, 100)
		self.volume_slider.setValue(70)
		self.player.audio_set_volume(70)
		self.volume_slider.valueChanged.connect(self.change_volume)
		layout.addWidget(self.volume_slider, 3, 1, 1, 2)

		self.time_label = QLabel("播放時間：00:00 / 00:00")
		layout.addWidget(self.time_label, 4, 0)

		self.position_slider = ClickableSlider(Qt.Horizontal)
		self.position_slider.setRange(0, 1000)
		self.position_slider.sliderMoved.connect(self.seek_position)
		layout.addWidget(self.position_slider, 4, 1, 1, 2)

		self.current_label = QLabel("正在播放：")
		self.current_title = MarqueeLabel(" ")
		layout.addWidget(self.current_label, 5, 0)
		layout.addWidget(self.current_title, 5, 1, 1, 2)


		self.list_widget = QListWidget()
		self.list_widget.itemDoubleClicked.connect(self.select_song)
		layout.addWidget(self.list_widget, 6, 0, 1, 3)  # 橫跨兩欄

		self.setLayout(layout)

	def load_playlist(self):
		url = self.url_input.text()
		ydl_opts = {
			'quiet': True,
			'extract_flat': 'in_playlist',
			'force_generic_extractor': True,
		}

		def fetch():
			with YoutubeDL(ydl_opts) as ydl:
				info = ydl.extract_info(url, download=False)

				entries = info.get('entries', [info])
				for entry in entries:
					video_url = f"https://www.youtube.com/watch?v={entry['id']}" if 'id' in entry else entry['url']
					title = entry.get('title', video_url)
					self.playlist.append({'title': title, 'url': video_url})
					self.list_widget.addItem(title)

		threading.Thread(target=fetch).start()

	def play_music(self):
		if not self.playlist:
			return

		self.player.stop()
		self.cleanup_temp_file()

		entry = self.playlist[self.current_index]
		self.current_title.setText(f"{entry['title']}")
		self.list_widget.setCurrentRow(self.current_index)
		self.temp_filepath = None  # 清除前次路徑

		def fetch_and_play():
			ydl_opts = {
					"format": "bestaudio/best",
					"extractaudio": True,
					"audioformat": "mp3",
					"outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
					"restrictfilenames": True,
					"noplaylist": True,
					"nocheckcertificate": True,
					"ignoreerrors": False,
					"logtostderr": False,
					"quiet": True,
					"no_warnings": True,
					"default_search": "auto",
					"source_address": "0.0.0.0",
					"force-ipv4": True,
					"cachedir": False,
					"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
			}

			try:
				with YoutubeDL(ydl_opts) as ydl:
					info = ydl.extract_info(entry['url'], download=False)
					stream_url = info['url']
					media = self.instance.media_new(stream_url)
					self.player.set_media(media)
					self.player.play()
					time.sleep(3)
					if self.player.get_state() == vlc.State.Error:
						raise Exception("Stream failed")
			except:
				print("串流失敗，改為下載音訊播放")
				with YoutubeDL(ydl_opts) as ydl:
					info = ydl.extract_info(entry['url'], download=True)
					self.temp_filepath = ydl.prepare_filename(info)
					media = self.instance.media_new(os.path.abspath(self.temp_filepath))
					self.player.set_media(media)
					self.player.play()

		threading.Thread(target=fetch_and_play).start()

	def cleanup_temp_file(self):
		if self.temp_filepath and os.path.exists(self.temp_filepath):
			try:
				os.remove(self.temp_filepath)
				print(f"已刪除暫存檔：{self.temp_filepath}")
			except Exception as e:
				print(f"刪除檔案失敗：{e}")
		self.temp_filepath = None

	def update_playlist_widget(self):
		self.list_widget.clear()

		for video in self.playlist:
			self.list_widget.addItem(video["title"])

	def toggle_pause(self):
		if self.player.is_playing():
			self.player.pause()
			self.pause_button.setText("⏯️ 繼續")
		else:
			self.player.play()
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
		self.update_playlist_widget()

	def search_lyrics(self):
		self.tray_icon.showMessage(
				"YouTube 音樂播放器",
				"正在搜尋歌詞，找到會自動開啟網頁(可能會找到錯誤的歌曲)",
				QSystemTrayIcon.Information,
				3000
			)
		
		current_song = self.playlist[self.current_index]["title"]
		ai_title = AI_title()
		true_title = ai_title.ask_ai(f"請給我這首歌的歌名 只要歌名就好\n{current_song}")
		lyrics_url = self.get_lyrics(true_title)

		webbrowser.get('windows-default').open_new(lyrics_url)

	def get_lyrics(self, title):
		client_access_token = "aW0PCZtUaF6ol8tBEFw6iAQ0dYakXRLpb_1nYzoOJBnAIbzctmdBK7c3IvcvE5Hs"
		url = f"http://api.genius.com/search?q={title}&access_token={client_access_token}"

		try:
			response = requests.get(url)
			json_data = response.json()

			song = json_data['response']['hits'][0]['result']['relationships_index_url']
			return song
		except Exception as e:
			print(e)
			return None

	def change_volume(self, value):
		self.player.audio_set_volume(value)
		self.volume_label.setText(f"音量：{value}")

	def select_song(self):
		row = self.list_widget.currentRow()
		if row != -1:
			self.current_index = row
			self.play_music()

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
			"""攔截視窗關閉事件，改為隱藏視窗"""
			event.ignore()          # 忽略預設關閉事件
			self.hide()             # 隱藏視窗
			self.tray_icon.showMessage(
				"YouTube 音樂播放器",
				"程式已隱藏至通知列。",
				QSystemTrayIcon.Information,
				3000
			)

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
