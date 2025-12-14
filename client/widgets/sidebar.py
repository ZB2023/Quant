from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject
import requests
import urllib3
from client.widgets.avatar_view import CircularAvatar, AvatarViewer

urllib3.disable_warnings()

class FetcherSignals(QObject):
    done = Signal(bytes)

class Fetcher(QRunnable):
    def __init__(self, api, u):
        super().__init__()
        self.api = api
        self.u = u
        self.signals = FetcherSignals()

    def run(self):
        try:
            r = requests.get(f"{self.api}/user/profile_info", params={"username": self.u}, verify=False, timeout=5)
            if r.status_code == 200:
                u = r.json().get('avatar_url')
                if u:
                    if u.startswith("/"):
                        u = f"{self.api}{u}"
                    res = requests.get(u, verify=False, timeout=5)
                    self.signals.done.emit(res.content)
        except:
            pass

class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(260)
        self.setObjectName("Sidebar")
        self.api_url = "https://localhost:8001"
        self.u_name = "Guest"

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

    def set_api_url(self, u):
        self.api_url = u

    def set_username(self, n):
        self.u_name = n
        self.n_lbl.setText(n)
        self.reload_avatar()

    def reload_avatar(self):
        self.av.set_letter(self.u_name)
        f = Fetcher(self.api_url, self.u_name)
        f.signals.done.connect(self.av.set_data)
        QThreadPool.globalInstance().start(f)