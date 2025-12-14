# client/widgets/friends_page.py
import requests
import urllib3
import hashlib
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QFrame, QScrollArea,
    QGraphicsDropShadowEffect, QMessageBox,
    QGraphicsOpacityEffect, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QRunnable, QThreadPool, QObject, QPropertyAnimation, QSize, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush
from client.widgets.avatar_view import CircularAvatar

urllib3.disable_warnings()
API_URL = "https://localhost:8001"

class WorkerSignals(QObject):
    finished = Signal()
    loaded = Signal(bytes)
    incoming = Signal(list)
    friends = Signal(list)
    blocked = Signal(list)

class AvatarLoader(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.signals = WorkerSignals()
        self.url = url

    def run(self):
        if not self.url:
            self.signals.loaded.emit(b"")
            self.signals.finished.emit()
            return
        
        try:
            target = self.url
            if target and not target.startswith("http"):
                target = f"{API_URL}/{target}"
            
            r = requests.get(target, verify=False, timeout=5)
            if r.status_code == 200:
                self.signals.loaded.emit(r.content)
            else:
                self.signals.loaded.emit(b"")
        except:
            self.signals.loaded.emit(b"")
        finally:
            self.signals.finished.emit()

class FriendsLoader(QRunnable):
    def __init__(self, user):
        super().__init__()
        self.signals = WorkerSignals()
        self.user = user

    def run(self):
        if not self.user:
            self.signals.finished.emit()
            return
        
        try:
            r1 = requests.get(f"{API_URL}/friends/incoming", params={"user": self.user}, verify=False, timeout=3)
            if r1.status_code == 200:
                self.signals.incoming.emit(r1.json().get("requests", []))
            
            r2 = requests.get(f"{API_URL}/friends/list", params={"user": self.user}, verify=False, timeout=3)
            if r2.status_code == 200:
                self.signals.friends.emit(r2.json().get("friends", []))

            r3 = requests.get(f"{API_URL}/blacklist/list", params={"user": self.user}, verify=False, timeout=3)
            if r3.status_code == 200:
                self.signals.blocked.emit(r3.json().get("blocked", []))
        except:
            pass
        finally:
            self.signals.finished.emit()

class ActionIconBtn(QPushButton):
    def __init__(self, mode, color_hex, size=36, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.mode = mode
        self.base_color = QColor(color_hex)
        self.hover = False

    def enterEvent(self, e):
        self.hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        bg = self.base_color if self.hover else QColor(255, 255, 255, 15)
        fg = QColor("white") if self.hover else self.base_color

        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 8, 8)

        p.setPen(QPen(fg, 2))
        p.setBrush(Qt.NoBrush)

        c = self.rect().center()
        cx, cy = c.x(), c.y()

        if self.mode == "msg":
            path = QPainterPath()
            path.addRoundedRect(cx - 9, cy - 8, 18, 14, 4, 4)
            path.moveTo(cx - 4, cy + 6)
            path.lineTo(cx - 9, cy + 10)
            path.lineTo(cx, cy + 6)
            p.drawPath(path)

        elif self.mode == "del":
            p.drawRect(cx - 5, cy - 4, 10, 10)
            p.drawLine(cx - 7, cy - 4, cx + 7, cy - 4)
            p.drawLine(cx - 2, cy - 7, cx + 2, cy - 7)
            p.drawLine(cx - 2, cy - 2, cx - 2, cy + 4)
            p.drawLine(cx + 2, cy - 2, cx + 2, cy + 4)

        elif self.mode == "block":
            p.drawEllipse(c, 8, 8)
            p.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
        
        elif self.mode == "reject":
            p.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            p.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)

class LoadingStateWidget(QWidget):
    def __init__(self, text="Синхронизация данных..."):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        self.layout.setContentsMargins(0, 40, 0, 40)

        self.lbl_icon = QLabel("⟳")
        self.lbl_icon.setStyleSheet("font-size: 36px; font-weight: bold;")
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        
        self.lbl_text = QLabel(text)
        self.lbl_text.setObjectName("SubTitle")
        self.lbl_text.setAlignment(Qt.AlignCenter)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(1000)
        self.anim.setStartValue(0.4)
        self.anim.setEndValue(1.0)
        self.anim.setLoopCount(-1)
        self.anim.setKeyValueAt(0.5, 1.0)
        self.anim.setKeyValueAt(1.0, 0.4)
        
        self.layout.addWidget(self.lbl_icon)
        self.layout.addWidget(self.lbl_text)
        
        self.anim.start()

class ToastNotification(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(300, 50)
        self.hide()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        self.lbl_text = QLabel("")
        self.lbl_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_text)
        
        self.timer_hide = QTimer(self)
        self.timer_hide.setSingleShot(True)
        self.timer_hide.timeout.connect(self.hide)

    def show_message(self, text, bg_color="#22c55e"):
        self.lbl_text.setText(text)
        self.setStyleSheet(f"QFrame{{background-color: {bg_color}; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2);}} QLabel{{color:white; font-weight:bold; font-size:14px; border:none;}}")
        
        if self.parentWidget():
            self.move((self.parentWidget().width() - self.width()) // 2, self.parentWidget().height() - 80)
        
        self.show()
        self.raise_()
        self.timer_hide.start(3000)

class FriendCard(QFrame):
    action_clicked = Signal(str, str)

    def __init__(self, user_data, mode="friend"):
        super().__init__()
        
        if isinstance(user_data, dict):
            self.username = user_data.get('username', 'Unknown')
            self.avatar_url = user_data.get('avatar_url')
        else:
            self.username = str(user_data)
            self.avatar_url = None

        self.setFixedHeight(80)
        
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(15)
        sh.setYOffset(4)
        sh.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(sh)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(15, 10, 15, 10)
        lay.setSpacing(15)

        self.avatar_widget = CircularAvatar(50)
        self.avatar_widget.set_letter(self.username)
        
        if self.avatar_url:
            self.loader = AvatarLoader(self.avatar_url)
            self.loader.signals.loaded.connect(self.avatar_widget.set_data)
            QThreadPool.globalInstance().start(self.loader)
        
        info = QVBoxLayout()
        info.setSpacing(2)
        info.setAlignment(Qt.AlignVCenter)
        
        nm = QLabel(self.username)
        nm.setObjectName("Header")
        nm.setStyleSheet("font-size: 16px; border:none;")
        
        st = QLabel()
        st.setStyleSheet("font-size: 12px; border:none;")
        
        if mode == 'friend':
            st.setText("В сети")
            st.setStyleSheet(st.styleSheet() + " color: #4ade80;")
        elif mode == 'incoming':
            st.setText("Входящая заявка")
            st.setStyleSheet(st.styleSheet() + " color: #6366f1;")
        elif mode == 'blocked':
            st.setText("В ЧС")
            st.setStyleSheet(st.styleSheet() + " color: #ef4444;")

        info.addWidget(nm)
        info.addWidget(st)

        btns = QHBoxLayout()
        btns.setSpacing(8)

        if mode == 'friend':
            b_msg = ActionIconBtn("msg", "#6366f1")
            b_msg.setToolTip("Написать сообщение")
            b_msg.clicked.connect(lambda: self.action_clicked.emit("write", self.username))
            
            b_del = ActionIconBtn("del", "#ef4444")
            b_del.setToolTip("Удалить из друзей")
            b_del.clicked.connect(lambda: self.action_clicked.emit("delete", self.username))

            b_blk = ActionIconBtn("block", "#f59e0b")
            b_blk.setToolTip("Заблокировать")
            b_blk.clicked.connect(lambda: self.action_clicked.emit("block", self.username))

            btns.addWidget(b_msg)
            btns.addWidget(b_del)
            btns.addWidget(b_blk)

        elif mode == 'incoming':
            acc = QPushButton("Принять")
            acc.setFixedSize(90, 36)
            acc.setCursor(Qt.PointingHandCursor)
            acc.setStyleSheet("background-color:#22c55e; color:white; border-radius:8px; font-weight:bold; border:none;")
            acc.clicked.connect(lambda: self.action_clicked.emit("accept", self.username))
            btns.addWidget(acc)
            
            rej = ActionIconBtn("reject", "#9ca3af")
            rej.setToolTip("Отклонить")
            rej.clicked.connect(lambda: self.action_clicked.emit("delete", self.username))
            btns.addWidget(rej)

        elif mode == 'blocked':
            un = QPushButton("Разблок.")
            un.setFixedHeight(36)
            un.setCursor(Qt.PointingHandCursor)
            un.setStyleSheet("background:transparent; border:1px solid #4ade80; color:#4ade80; border-radius:8px; padding:0 10px;")
            un.clicked.connect(lambda: self.action_clicked.emit("unblock", self.username))
            btns.addWidget(un)

        lay.addWidget(self.avatar_widget)
        lay.addLayout(info)
        lay.addStretch()
        lay.addLayout(btns)

class SectionHeader(QLabel):
    def __init__(self, t):
        super().__init__(t)
        self.setObjectName("SectionTitle")

class FriendsPage(QWidget):
    start_chat_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self._is_alive = True
        
        self.username = ""
        self.current_incoming = None
        self.current_friends = None
        self.current_blocked = None
        self.filter_text = ""
        self.is_loading = False
        
        # 1. СОЗДАЕМ TOAST ДО ПОСТРОЕНИЯ ИНТЕРФЕЙСА
        self.toast = ToastNotification(self) 

        # 2. Создаем таймер, но НЕ запускаем его (автостарт убрали)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_friends)

        # 3. Теперь строим интерфейс
        self.init_ui()

    def init_ui(self):
        m = QVBoxLayout(self)
        m.setContentsMargins(30, 30, 30, 30)
        m.setSpacing(20)
        
        h = QHBoxLayout()
        t = QLabel("Друзья")
        t.setObjectName("Header")
        t.setStyleSheet("font-size:28px;")
        h.addWidget(t)
        h.addStretch()
        
        sc = QFrame()
        sc.setObjectName("AuthCard")
        sc.setFixedHeight(45)
        sc.setFixedWidth(320)
        sl = QHBoxLayout(sc)
        sl.setContentsMargins(10, 0, 5, 0)
        
        self.inp_add = QLineEdit()
        self.inp_add.setPlaceholderText("Логин друга для заявки...")
        self.inp_add.setStyleSheet("border:none; background:transparent;")
        
        btn_r = QPushButton("Отправить")
        btn_r.setObjectName("PrimaryBtn")
        btn_r.setFixedHeight(30)
        btn_r.clicked.connect(self.send_request)
        
        sl.addWidget(self.inp_add)
        sl.addWidget(btn_r)
        h.addWidget(sc)
        m.addLayout(h)

        fb = QHBoxLayout()
        fl = QLabel("Поиск:")
        fl.setObjectName("SubTitle")
        
        self.inp_filter = QLineEdit()
        self.inp_filter.setPlaceholderText("Фильтр списка...")
        self.inp_filter.textChanged.connect(self.on_filter)
        
        fb.addWidget(fl)
        fb.addWidget(self.inp_filter)
        m.addLayout(fb)

        sr = QScrollArea()
        sr.setWidgetResizable(True)
        sr.setStyleSheet("QScrollArea{border:none; background:transparent;} QWidget{background:transparent;}")
        
        self.cont = QWidget()
        self.cl = QVBoxLayout(self.cont)
        self.cl.setAlignment(Qt.AlignTop)
        self.cl.setSpacing(10)
        
        sr.setWidget(self.cont)
        m.addWidget(sr)
        
        self.render_all()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # проверка hasattr на случай раннего вызова
        if hasattr(self, 'toast') and self.toast.isVisible():
            self.toast.move((self.width() - 300) // 2, self.height() - 80)

    def set_user(self, u):
        # Сначала останавливаем всё старое
        self.stop_all_workers()
        
        self.username = u
        self.current_incoming = None
        self.current_friends = None
        self.current_blocked = None
        
        # Очищаем интерфейс перед загрузкой
        while self.cl.count():
            it = self.cl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            
        if not self.username:
            return

        self.render_all()
        self.load_friends()
        # Запускаем таймер только если есть пользователь
        if not self.timer.isActive():
            self.timer.start(5000)

    def load_friends(self):
        if not self.username or self.is_loading:
            return
        
        self.is_loading = True
        loader = FriendsLoader(self.username)
        loader.signals.incoming.connect(self.upd_in)
        loader.signals.friends.connect(self.upd_fr)
        loader.signals.blocked.connect(self.upd_bl)
        loader.signals.finished.connect(self.on_loader_finished)
        QThreadPool.globalInstance().start(loader)

    def on_loader_finished(self):
        self.is_loading = False

    # Модифицируйте колбэки обновления данных
    def upd_in(self, d):
        if not self._is_alive: return # <--- ЗАЩИТА
        if d != self.current_incoming:
            self.current_incoming = d
            self.render_all()
    
    def upd_fr(self, d):
        if not self._is_alive: return # <--- ЗАЩИТА
        if d != self.current_friends:
            self.current_friends = d
            self.render_all()
    
    def upd_bl(self, d):
        if not self._is_alive: return # <--- ЗАЩИТА
        if d != self.current_blocked:
            self.current_blocked = d
            self.render_all()

    def on_filter(self, t):
        self.filter_text = t.lower()
        self.render_all()

    def render_all(self):
        while self.cl.count():
            it = self.cl.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        if self.current_friends is None:
            self.cl.addStretch()
            self.cl.addWidget(LoadingStateWidget())
            self.cl.addStretch()
            return

        inc = self.current_incoming or []
        if inc:
            self.cl.addWidget(SectionHeader(f"Входящие ({len(inc)})"))
            for u_data in inc:
                c = FriendCard(u_data, "incoming")
                c.action_clicked.connect(self.act)
                self.cl.addWidget(c)

        fr = self.current_friends or []
        vis = []
        for f_data in fr:
            nm = f_data.get('username') if isinstance(f_data, dict) else f_data
            if self.filter_text in nm.lower():
                vis.append(f_data)
        
        self.cl.addWidget(SectionHeader(f"Мои друзья ({len(vis)})"))
        if not vis:
            l = QLabel("Список друзей пуст.\nДобавьте кого-нибудь через поле выше.")
            l.setObjectName("SubTitle")
            l.setStyleSheet("font-style:italic; margin-top:20px; font-size:14px;")
            l.setAlignment(Qt.AlignCenter)
            self.cl.addWidget(l)
        else:
            for f_data in vis:
                c = FriendCard(f_data, "friend")
                c.action_clicked.connect(self.act)
                self.cl.addWidget(c)

        bl = self.current_blocked or []
        if bl:
            self.cl.addWidget(SectionHeader(f"Черный список ({len(bl)})"))
            for b_data in bl:
                c = FriendCard(b_data, "blocked")
                c.action_clicked.connect(self.act)
                self.cl.addWidget(c)
        
        self.cl.addStretch()

    def send_request(self):
        tgt = self.inp_add.text().strip()
        if not tgt:
            return
        if tgt == self.username:
            self.toast.show_message("Нельзя добавить себя", "#ef4444")
            self.inp_add.clear()
            return
        
        self.api("/friends/request", {"me": self.username, "target": tgt})
        self.inp_add.clear()
        self.toast.show_message(f"Заявка отправлена: {tgt}", "#3b82f6")

    def act(self, action, tgt):
        if action == "write":
            self.start_chat_requested.emit(tgt)
            return
        
        ep, msg, destr = "", "", False
        
        if action == "accept":
            ep = "/friends/accept"
            msg = f"Дружба принята: {tgt}"
        elif action == "delete":
            if QMessageBox.question(self, "?", f"Удалить {tgt}?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            ep = "/friends/remove"
            msg = f"{tgt} удален"
            destr = True
        elif action == "block":
            if QMessageBox.question(self, "??", f"В ЧС: {tgt}?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            ep = "/blacklist/block"
            msg = f"{tgt} заблокирован"
            destr = True
        elif action == "unblock":
            ep = "/blacklist/unblock"
            msg = f"{tgt} разблокирован"

        if ep:
            self.api(ep, {"me": self.username, "target": tgt})
            self.toast.show_message(msg, "#ef4444" if destr else "#22c55e")
            self.current_friends = None
            self.render_all()
            QTimer.singleShot(200, self.load_friends)

    def api(self, ep, d):
        QTimer.singleShot(0, lambda: requests.post(f"{API_URL}{ep}", json=d, verify=False))

    def stop_all_workers(self):
        if hasattr(self, 'timer'):
            self.timer.stop()
        self.is_loading = False
        
    def closeEvent(self, e):
        self._is_alive = False
        self.stop_all_workers()
        super().closeEvent(e)