from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject
import requests
import urllib3
from client.widgets.avatar_view import CircularAvatar, AvatarViewer
urllib3.disable_warnings()
API_URL = "https://localhost:8001"

class FetcherSignals(QObject):
    done = Signal(bytes)

class Fetcher(QRunnable):
    def __init__(self, api, u):
        super().__init__()
        self.api = api
        self.u = u
        self.signals = FetcherSignals()
        self.setAutoDelete(True) # Важно: автоудаление
        
    def run(self):
        try:
            # Делаем короткий таймаут
            r = requests.get(f"{self.api}/user/profile_info", params={"username": self.u}, verify=False, timeout=3)
            if r.status_code == 200:
                u = r.json().get('avatar_url')
                if u:
                    if u.startswith("/"):
                        u = f"{self.api}{u}"
                    res = requests.get(u, verify=False, timeout=3)
                    self.signals.done.emit(res.content)
        except:
            pass

class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(260)
        self.setObjectName("Sidebar")
        self.u_name = "Guest"
        self._is_alive = True  # Флаг жизни виджета

        l = QVBoxLayout(self)
        l.setContentsMargins(20, 40, 20, 20)
        l.setSpacing(10)
        self.av = CircularAvatar(80)
        self.av.set_letter("G")
        self.av.clicked.connect(self.open_preview)
        self.n_lbl = QLabel("Guest")
        self.n_lbl.setAlignment(Qt.AlignCenter)
        self.n_lbl.setObjectName("UsernameLabel")
        l.addWidget(self.av, 0, Qt.AlignCenter)
        l.addWidget(self.n_lbl)
        l.addSpacing(30)
        self.btn_profile = self.btn("👤 Профиль")
        self.btn_feed = self.btn("📰 Лента")
        self.btn_media = self.btn("🎵 Медиатека")
        self.btn_friends = self.btn("👥 Друзья")
        self.btn_msg = self.btn("💬 Сообщения")
        self.btn_settings = self.btn("⚙️ Настройки")
        l.addWidget(self.btn_profile)
        l.addWidget(self.btn_feed)
        l.addWidget(self.btn_media)
        l.addWidget(self.btn_friends)
        l.addWidget(self.btn_msg)
        l.addWidget(self.btn_settings)
        l.addStretch()

    def open_preview(self):
        if self.av.raw_data:
            AvatarViewer(self.av.raw_data, self.window()).exec()

    def btn(self, txt):
        b = QPushButton(txt)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(45)
        b.setObjectName("NavBtn")
        return b

    def set_username(self, n):
        self.u_name = n
        self.n_lbl.setText(n)
        self.reload_avatar()

    def reload_avatar(self):
        self.av.set_letter(self.u_name)
        f = Fetcher(API_URL, self.u_name)
        f.signals.done.connect(self.on_avatar_loaded) # Подключаем не напрямую
        QThreadPool.globalInstance().start(f)

    def on_avatar_loaded(self, data):
        # ЗАЩИТА: Если виджет уже удален или помечен как мертвый, не трогаем UI
        if not self._is_alive: 
            return
        try:
            self.av.set_data(data)
        except RuntimeError:
            pass # Если вдруг C++ объект удален

    def closeEvent(self, event):
        self._is_alive = False
        super().closeEvent(event)