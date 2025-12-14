import hashlib
import requests
import urllib3
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QDialog, QPushButton, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject
from PySide6.QtGui import QColor
from client.widgets.avatar_view import CircularAvatar, AvatarViewer

urllib3.disable_warnings()
API_URL = "https://localhost:8001"

class PSignals(QObject):
    res = Signal(dict, bytes)

class PLoader(QRunnable):
    def __init__(self, u):
        super().__init__()
        self.u = u
        self.signals = PSignals()

    def run(self):
        d = {"friends": "0", "status": "", "bio": ""}
        ab = None
        try:
            r1 = requests.get(f"{API_URL}/friends/list", params={"user": self.u}, verify=False, timeout=3)
            if r1.status_code == 200:
                d["friends"] = str(len(r1.json().get("friends", [])))
            
            r2 = requests.get(f"{API_URL}/user/profile_info", params={"username": self.u}, verify=False, timeout=3)
            if r2.status_code == 200:
                j = r2.json()
                d["status"] = j.get("status_msg", "")
                d["bio"] = j.get("bio", "")
                u = j.get("avatar_url")
                if u:
                    if u.startswith("/"):
                        u = f"{API_URL}{u}"
                    ir = requests.get(u, verify=False, timeout=5)
                    if ir.status_code == 200:
                        ab = ir.content
        except:
            pass
        
        self.signals.res.emit(d, ab or b'')

class BaseProfileView(QWidget):
    def __init__(self, username=None, parent=None):
        super().__init__(parent)
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setAlignment(Qt.AlignCenter)
        self.layout_main.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        self.card.setObjectName("AuthCard")
        self.card.setFixedSize(550, 600)
        
        self.cl = QVBoxLayout(self.card)
        self.cl.setSpacing(10)
        self.cl.setContentsMargins(40, 40, 40, 40)
        
        self.av = CircularAvatar(140)
        self.av.clicked.connect(self.show_preview)
        
        self.cl.addWidget(self.av, 0, Qt.AlignHCenter)
        
        self.n = QLabel("Name")
        self.n.setObjectName("Header")
        self.n.setAlignment(Qt.AlignCenter)
        self.n.setStyleSheet("font-size: 24px;")
        
        self.h = QLabel("@handle")
        self.h.setObjectName("SubTitle")
        self.h.setAlignment(Qt.AlignCenter)
        
        self.s = QLabel("...")
        self.s.setObjectName("SubTitle")
        self.s.setAlignment(Qt.AlignCenter)
        self.s.setStyleSheet("color:#6366f1; font-weight:bold;")
        
        self.cl.addWidget(self.n)
        self.cl.addWidget(self.h)
        self.cl.addWidget(self.s)
        self.cl.addSpacing(10)
        
        self.b = QLabel("...")
        self.b.setWordWrap(True)
        self.b.setAlignment(Qt.AlignCenter)
        self.b.setObjectName("NormalText")
        self.b.setStyleSheet("background:rgba(127,127,127,0.1); border-radius:10px; padding:15px; margin:0 40px;")
        
        self.cl.addWidget(self.b)
        self.cl.addSpacing(20)
        
        r1 = QHBoxLayout()
        r1.setAlignment(Qt.AlignCenter)
        r1.setSpacing(40)
        self.l_id = self.st("ID", "0000")
        self.l_rg = self.st("JOINED", "2025")
        r1.addLayout(self.l_id)
        r1.addLayout(self.l_rg)
        
        r2 = QHBoxLayout()
        r2.setAlignment(Qt.AlignCenter)
        r2.setSpacing(40)
        self.l_fr = self.st("FRIENDS", "-")
        self.l_st = self.st("STATUS", "Online")
        r2.addLayout(self.l_fr)
        r2.addLayout(self.l_st)
        
        self.cl.addLayout(r1)
        self.cl.addSpacing(15)
        self.cl.addLayout(r2)
        self.cl.addStretch()
        self.layout_main.addWidget(self.card)
        
        if username:
            self.set_user(username)

    def show_preview(self):
        if self.av.raw_data:
            AvatarViewer(self.av.raw_data, self.window()).exec()

    def st(self, t, v):
        bl = QVBoxLayout()
        bl.setSpacing(2)
        l1 = QLabel(t)
        l1.setAlignment(Qt.AlignCenter)
        l1.setObjectName("SubTitle")
        l1.setStyleSheet("font-size:10px; font-weight:bold;")
        l2 = QLabel(v)
        l2.setAlignment(Qt.AlignCenter)
        l2.setObjectName("Val")
        l2.setStyleSheet("font-size:18px;")
        bl.addWidget(l1)
        bl.addWidget(l2)
        return bl

    def sv(self, lo, v):
        for i in range(lo.count()):
            w = lo.itemAt(i).widget()
            if w and w.objectName() == "Val":
                w.setText(str(v))

    def set_user(self, u):
        if not u:
            return
        self.usr = u
        self.n.setText(u)
        self.h.setText(f"@{u.lower()}")
        self.av.set_letter(u)
        m = hashlib.md5(u.encode()).hexdigest()
        self.sv(self.l_id, f"#{int(m, 16)%9999:04d}")
        self.refresh()

    def refresh(self):
        if hasattr(self, 'usr'):
            l = PLoader(self.usr)
            l.signals.res.connect(self.done)
            QThreadPool.globalInstance().start(l)

    def done(self, d, b):
        self.b.setText(d['bio'] or "No bio.")
        self.s.setText(d['status'] or "")
        self.sv(self.l_fr, d['friends'])
        if b:
            self.av.set_data(b)

class ProfilePage(BaseProfileView):
    pass

class ProfileViewDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(600, 650)

        l = QVBoxLayout(self)
        l.setContentsMargins(10, 10, 10, 10)
        
        self.prof = BaseProfileView(username)
        shadow = QGraphicsDropShadowEffect(self.prof.card)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.prof.card.setGraphicsEffect(shadow)
        
        self.btn_close = QPushButton("✕", self.prof.card)
        self.btn_close.setGeometry(500, 20, 30, 30)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setStyleSheet("border:none; color:#777; font-size:18px; font-weight:bold;")
        
        l.addWidget(self.prof)

    def mousePressEvent(self, e):
        self._dp = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        self.move(e.globalPosition().toPoint() - self._dp)