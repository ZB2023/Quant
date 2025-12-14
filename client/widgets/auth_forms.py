import requests
import urllib3
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QStackedWidget, QFrame, QMessageBox, 
    QCheckBox, QSizePolicy, QDialog, QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Signal, Qt, QThread, QObject, QSettings, QRect, QSize
)
from PySide6.QtGui import (
    QAction, QPainter, QPainterPath, QColor, QPen, QLinearGradient, QBrush, QFontMetrics
)

from client.styles import (
    AUTH_STYLES, get_icon, 
    SVG_USER, SVG_MAIL, SVG_LOCK, 
    SVG_EYE_OPEN, SVG_EYE_CLOSED,
    BORDER_INPUT, BORDER_FOCUS, ACCENT_COLOR, TEXT_WHITE
)

print("--- [LOAD] Loading Auth Forms (Painter Checkbox Fixed Sizing) ---")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
API_URL = "https://localhost:8001"

def update_global_api_url(new_url):
    global API_URL
    new_url = new_url.strip()
    if not new_url.startswith("http"):
        new_url = f"https://{new_url}"
    if new_url.count(":") < 2:
        if new_url.endswith("/"): new_url = new_url[:-1]
        new_url = f"{new_url}:8001"
    if new_url.endswith("/"): new_url = new_url[:-1]

    API_URL = new_url
    try:
        import client.widgets.friends_page
        client.widgets.friends_page.API_URL = new_url
    except ImportError: pass
    
    try:
        import client.widgets.settings_page
        client.widgets.settings_page.API_URL = new_url
    except ImportError: pass
    
    return API_URL

# --- WORKER ---
class NetworkWorker(QObject):
    finished = Signal(dict)
    
    def __init__(self, task_type, url, data=None):
        super().__init__()
        self.task_type = task_type
        self.url = url
        self.data = data

    def run(self):
        res = {"success": False, "msg": "", "code": 0}
        try:
            if self.task_type == "ping":
                r = requests.get(f"{self.url}/openapi.json", verify=False, timeout=2)
                res["code"] = r.status_code
                if r.status_code == 200:
                    res["success"] = True
            elif self.task_type == "login":
                r = requests.post(f"{self.url}/login", json=self.data, verify=False, timeout=4)
                res["code"] = r.status_code
                if r.status_code == 200:
                    res["success"] = True
            elif self.task_type == "register":
                r = requests.post(f"{self.url}/register", json=self.data, verify=False, timeout=4)
                res["code"] = r.status_code
                if r.status_code == 200:
                    res["success"] = True
        except Exception as e:
            res["msg"] = str(e)
        self.finished.emit(res)

# --- INNER EDIT ---
class InnerEdit(QLineEdit):
    focus_in = Signal()
    focus_out = Signal()
    
    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.focus_in.emit()
        
    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.focus_out.emit()

# --- CUSTOM PAINTED CHECKBOX ---
class PremiumCheckBox(QCheckBox):
    """
    Кастомный чекбокс с ручной отрисовкой галочки и корректным SizeHint,
    чтобы ничего не обрезалось layout'ом.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32) 
        
        # Размеры элементов (для расчетов в paintEvent и sizeHint)
        self.box_size = 22
        self.spacing = 10
        self.margin_left = 4  # Безопасный отступ слева, чтобы не касаться края виджета

    def sizeHint(self):
        # Рассчитываем точную ширину контента, чтобы Layout не плющил нас
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        total_width = self.margin_left + self.box_size + self.spacing + text_width + 10 # +10 запас
        return QSize(total_width, 32)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Центрирование квадратика по вертикали
        y_pos = (self.height() - self.box_size) // 2
        # Отступ слева, чтобы не резало
        x_pos = self.margin_left
        
        # Путь для фона квадратика
        path_bg = QPainterPath()
        path_bg.addRoundedRect(QRect(x_pos, y_pos, self.box_size, self.box_size), 6, 6)

        is_checked = self.isChecked()
        is_hover = self.underMouse()

        if is_checked:
            # Активный градиент (Индиго)
            grad = QLinearGradient(x_pos, y_pos, x_pos, y_pos + self.box_size)
            grad.setColorAt(0, QColor("#6366f1"))
            grad.setColorAt(1, QColor("#818cf8"))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawPath(path_bg)
            
            # РИСОВАНИЕ БЕЛОЙ ГАЛОЧКИ
            p.setPen(QPen(QColor("white"), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            
            check_path = QPainterPath()
            # Координаты внутри квадратика (относительно x_pos, y_pos)
            check_path.moveTo(x_pos + 5, y_pos + 11)  # Лево
            check_path.lineTo(x_pos + 9, y_pos + 16)  # Низ
            check_path.lineTo(x_pos + 17, y_pos + 6)  # Верх право
            
            p.drawPath(check_path)
            
        else:
            # Неактивный (темный)
            p.setBrush(QColor("#0F172A")) 
            # Цвет рамки
            border_col = QColor("#6366f1") if is_hover else QColor("#334155")
            p.setPen(QPen(border_col, 2))
            p.drawPath(path_bg)

        # ТЕКСТ
        p.setPen(QColor("#94A3B8"))
        p.setFont(self.font())
        
        text_x = x_pos + self.box_size + self.spacing
        text_rect = QRect(text_x, 0, self.width() - text_x, self.height())
        p.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text())

# --- QUANT INPUT ---
class QuantInput(QFrame):
    def __init__(self, icon_svg, alias_text, hint_text, is_password=False):
        super().__init__()
        self.alias_text = alias_text
        self.hint_text = hint_text
        self.title_text = alias_text
        
        self.setFixedHeight(56)
        self.setObjectName("QuantInputFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(0)
        
        self.lbl_title = QLabel(self.title_text)
        self.lbl_title.setFixedHeight(14)
        
        self.inp = InnerEdit()
        self.inp.setPlaceholderText(self.alias_text)
        self.inp.setFixedHeight(26)
        
        self.inp.setStyleSheet(f"""
            QLineEdit {{ 
                background: transparent; 
                border: none; 
                color: {TEXT_WHITE}; 
                font-size: 14px; 
                padding: 0px;
                selection-background-color: {ACCENT_COLOR};
            }}
        """)
        
        self.inp.focus_in.connect(self.on_focus_in)
        self.inp.focus_out.connect(self.on_focus_out)
        
        if icon_svg:
            self.inp.addAction(QAction(get_icon(icon_svg), "", self.inp), QLineEdit.LeadingPosition)
        
        if is_password:
            self.inp.setEchoMode(QLineEdit.Password)
            self.toggle_action = QAction(self.inp)
            self.icon_closed = get_icon(SVG_EYE_CLOSED)
            self.icon_open = get_icon(SVG_EYE_OPEN)
            self.toggle_action.setIcon(self.icon_closed)
            self.toggle_action.triggered.connect(self.toggle_visibility)
            self.inp.addAction(self.toggle_action, QLineEdit.TrailingPosition)
            
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.inp)

        self.update_view(False)

    def toggle_visibility(self):
        if self.inp.echoMode() == QLineEdit.Password:
            self.inp.setEchoMode(QLineEdit.Normal)
            self.toggle_action.setIcon(self.icon_open)
        else:
            self.inp.setEchoMode(QLineEdit.Password)
            self.toggle_action.setIcon(self.icon_closed)

    def text(self): return self.inp.text()
    
    def setText(self, text):
        self.inp.setText(text)
        self.update_view(bool(text))

    def clear(self):
        self.inp.clear()
        self.update_view(False)

    def on_focus_in(self): self.update_view(True)
    def on_focus_out(self): self.update_view(bool(self.inp.text().strip()))

    def update_view(self, active_state):
        is_focused = self.inp.hasFocus()
        border_col = BORDER_FOCUS if is_focused else BORDER_INPUT
        bg_col = "#151e32" if is_focused else "#0F172A"
        
        if active_state:
            lbl_color = ACCENT_COLOR
            ph_text = self.hint_text 
        else:
            lbl_color = "transparent"
            ph_text = self.alias_text

        self.setStyleSheet(f"QFrame#QuantInputFrame {{ background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 12px; }}")
        self.lbl_title.setStyleSheet(f"QLabel {{ color: {lbl_color}; font-family: 'Segoe UI'; font-size: 11px; font-weight: bold; border: none; background: transparent; }}")
        self.inp.setPlaceholderText(ph_text)

# --- SERVER CONFIG ---
class ServerConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки соединения")
        self.setFixedSize(360, 240)
        self.setStyleSheet("""
            QDialog { background-color: #1e293b; color: #f8fafc; }
            QLabel { color: #cbd5e1; font-family: 'Segoe UI'; font-size: 14px; }
            QLineEdit { 
                background: #0f172a; border: 1px solid #334155; 
                border-radius: 8px; color: white; padding: 12px; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #6366f1; }
            QPushButton { 
                background-color: #6366f1; color: white; border-radius: 8px; 
                font-weight: bold; border: none; height: 40px; font-family: 'Segoe UI';
            }
            QPushButton:hover { background-color: #4f46e5; }
            QPushButton:disabled { background-color: #334155; color: #94a3b8; }
        """)
        l = QVBoxLayout(self)
        l.setSpacing(15); l.setContentsMargins(20, 20, 20, 20)
        
        l.addWidget(QLabel("IP-адрес сервера", styleSheet="font-size: 18px; font-weight: 700; color: white;"))
        l.addWidget(QLabel("Укажите адрес сервера для проверки соединения:"))

        self.inp_url = QLineEdit()
        self.inp_url.setText(API_URL.replace("https://", "").replace(":8001", ""))
        l.addWidget(self.inp_url)

        self.status_bar = QLabel("")
        self.status_bar.setStyleSheet("font-size: 12px; margin-top: 5px;")
        l.addWidget(self.status_bar)

        self.btn_check = QPushButton("Проверить и Сохранить")
        self.btn_check.setCursor(Qt.PointingHandCursor)
        self.btn_check.clicked.connect(self.start_check)
        l.addWidget(self.btn_check)

    def start_check(self):
        full_url = update_global_api_url(self.inp_url.text().strip() or "localhost")
        self.btn_check.setEnabled(False); self.btn_check.setText("Проверка...")
        self.status_bar.setText(f"Подключение к {full_url}...")
        self.status_bar.setStyleSheet("color: #fbbf24;")
        
        self.thread = QThread()
        self.worker = NetworkWorker("ping", full_url)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.done)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def done(self, res):
        self.btn_check.setEnabled(True); self.btn_check.setText("Проверить и Сохранить")
        if res["success"]:
            self.status_bar.setStyleSheet("color: #4ade80; font-weight: bold;")
            self.status_bar.setText("✓ Доступен.")
            QMessageBox.information(self, "Успешно", "Соединение установлено!")
            self.accept()
        else:
            self.status_bar.setStyleSheet("color: #f87171;")
            self.status_bar.setText(f"Ошибка: {res['msg'] or res['code']}")

# --- LOGIN CARD ---
class LoginView(QWidget):
    login_success = Signal(str)
    go_to_reg = Signal()
    go_to_restore = Signal() 
    go_to_lan = Signal()

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        
        self.card = QFrame()
        self.card.setObjectName("AuthCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40); shadow.setColor(QColor(0,0,0,80)); shadow.setYOffset(10)
        self.card.setGraphicsEffect(shadow)

        l = QVBoxLayout(self.card)
        l.setSpacing(15); l.setContentsMargins(40,40,40,40)

        t = QLabel("Quant Desktop")
        t.setObjectName("AppTitle"); t.setAlignment(Qt.AlignCenter)
        st = QLabel("Войдите в аккаунт")
        st.setObjectName("SubTitle"); st.setAlignment(Qt.AlignCenter)

        # Инпуты
        self.inp_login = QuantInput(SVG_USER, "Логин", "Ваше имя пользователя")
        self.inp_pass = QuantInput(SVG_LOCK, "Пароль", "••••••", is_password=True)
        
        # --- ПРЕМИУМ CHECKBOX (Custom Painted) ---
        self.chk_remember = PremiumCheckBox("Запомнить меня")
        
        # Кнопки
        self.btn_enter = QPushButton("Войти в систему")
        self.btn_enter.setObjectName("PrimaryBtn")
        self.btn_enter.setFixedHeight(50)
        self.btn_enter.setCursor(Qt.PointingHandCursor)
        self.btn_enter.clicked.connect(self.do_login)

        link_l = QHBoxLayout()
        link_l.addStretch() 
        link_l.addWidget(QLabel("Нет аккаунта?", objectName="SmallText"))
        self.btn_reg = QPushButton("Создать аккаунт")
        self.btn_reg.setObjectName("LinkBtn")
        self.btn_reg.setCursor(Qt.PointingHandCursor)
        self.btn_reg.clicked.connect(self.go_to_reg.emit)
        link_l.addWidget(self.btn_reg)
        link_l.addStretch()

        ft = QHBoxLayout(); ft.setSpacing(20)
        btn_lan = QPushButton("📡 P2P Чат")
        btn_lan.setObjectName("LinkBtn"); btn_lan.setStyleSheet("color: #4ade80; font-size: 13px;") 
        btn_lan.clicked.connect(lambda: self.go_to_lan.emit())
        btn_set = QPushButton("⚙ Подключение")
        btn_set.setObjectName("LinkBtn"); btn_set.setStyleSheet("color: #94a3b8; font-size: 13px;")
        btn_set.clicked.connect(self.open_set)
        ft.addStretch(); ft.addWidget(btn_lan); ft.addWidget(QLabel("|", styleSheet="color:#334155"))
        ft.addWidget(btn_set); ft.addStretch()

        l.addWidget(t); l.addWidget(st); l.addSpacing(15)
        l.addWidget(self.inp_login)
        l.addWidget(self.inp_pass)
        
        # ЦЕНТРИРОВАНИЕ ЧЕКБОКСА (Safe Layout)
        chk_container = QHBoxLayout()
        chk_container.setContentsMargins(0, 5, 0, 5) # Смягчили марджины
        chk_container.addStretch()
        chk_container.addWidget(self.chk_remember)
        chk_container.addStretch()
        l.addLayout(chk_container)
        
        l.addWidget(self.btn_enter); l.addSpacing(5)
        l.addLayout(link_l); l.addSpacing(15)
        l.addLayout(ft)

        main_layout.addWidget(self.card)
        self.load_sets()

    def open_set(self): ServerConfigDialog(self).exec()

    # --- SETTINGS ---
    def load_sets(self):
        s = QSettings("QuantProject", "QuantDesktop")
        if s.value("remember", "false") == "true":
            self.inp_login.setText(s.value("login", ""))
            self.inp_pass.setText(s.value("password", ""))
            self.chk_remember.setChecked(True)

    def save_sets(self, l, p):
        s = QSettings("QuantProject", "QuantDesktop")
        if self.chk_remember.isChecked():
            s.setValue("login", l); s.setValue("password", p); s.setValue("remember", "true")
        else:
            s.remove("login"); s.remove("password"); s.setValue("remember", "false")

    def do_login(self):
        u = self.inp_login.text().strip()
        p = self.inp_pass.text().strip()
        if not u or not p: return

        self.btn_enter.setEnabled(False); self.btn_enter.setText("Вход...")
        self.thread = QThread()
        self.worker = NetworkWorker("login", API_URL, {"login": u, "pw": p})
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_fin)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_fin(self, r):
        self.btn_enter.setEnabled(True); self.btn_enter.setText("Войти в систему")
        if r["success"]:
            self.save_sets(self.inp_login.text(), self.inp_pass.text())
            self.login_success.emit(self.inp_login.text())
        elif r["code"]==401: QMessageBox.warning(self, "Err", "Неверный логин/пароль")
        else: QMessageBox.critical(self, "Err", "Ошибка сети")

# --- REGISTRATION ---
class RegisterView(QWidget):
    go_back = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.card = QFrame(objectName="AuthCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40); shadow.setColor(QColor(0,0,0,80)); shadow.setYOffset(10)
        self.card.setGraphicsEffect(shadow)

        l = QVBoxLayout(self.card)
        l.setSpacing(12); l.setContentsMargins(40,40,40,40)
        
        t = QLabel("Регистрация")
        t.setObjectName("AppTitle"); t.setAlignment(Qt.AlignCenter)

        self.inp_l = QuantInput(SVG_USER, "Логин", "User")
        self.inp_e = QuantInput(SVG_MAIL, "Email", "mail@ex.com")
        self.inp_p1 = QuantInput(SVG_LOCK, "Пароль", "***", True)
        self.inp_p2 = QuantInput(SVG_LOCK, "Повтор", "***", True)
        
        self.btn_r = QPushButton("Зарегистрироваться")
        self.btn_r.setObjectName("PrimaryBtn"); self.btn_r.setFixedHeight(50)
        self.btn_r.clicked.connect(self.do_reg)
        
        bb = QPushButton("Уже есть аккаунт? Войти")
        bb.setObjectName("LinkBtn"); bb.clicked.connect(self.go_back.emit)

        l.addWidget(t); l.addSpacing(10)
        l.addWidget(self.inp_l); l.addWidget(self.inp_e); l.addWidget(self.inp_p1); l.addWidget(self.inp_p2)
        l.addSpacing(10); l.addWidget(self.btn_r); l.addWidget(bb)
        layout.addWidget(self.card)

    def do_reg(self):
        if self.inp_p1.text() != self.inp_p2.text():
            QMessageBox.warning(self,"!","Пароли не совпадают"); return
        
        self.btn_r.setEnabled(False); self.btn_r.setText("...")
        self.thread = QThread()
        self.worker = NetworkWorker("register", API_URL, {
            "login": self.inp_l.text(), "email": self.inp_e.text(), "pw": self.inp_p1.text()
        })
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.fin)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def fin(self, r):
        self.btn_r.setEnabled(True); self.btn_r.setText("Зарегистрироваться")
        if r["success"]:
            QMessageBox.information(self,"OK", "Аккаунт создан!"); self.go_back.emit()
        else: QMessageBox.warning(self,"Err", r['msg'])

class RestoreView(QWidget):
    go_back = Signal()
    def __init__(self):
        super().__init__()
        l = QVBoxLayout(self); l.setAlignment(Qt.AlignCenter)
        c = QFrame(objectName="AuthCard")
        cl = QVBoxLayout(c); cl.setContentsMargins(40,40,40,40)
        cl.addWidget(QLabel("Функция отключена", objectName="SubTitle"))
        b = QPushButton("Назад", objectName="LinkBtn", clicked=self.go_back.emit)
        cl.addWidget(b); l.addWidget(c)

class AuthPage(QWidget):
    login_success = Signal(str)
    go_to_lan_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("AuthContainer")
        self.setStyleSheet(AUTH_STYLES)
        self.st = QStackedWidget()
        self.lv = LoginView()
        self.rv = RegisterView()
        self.rsv = RestoreView()
        self.st.addWidget(self.lv)
        self.st.addWidget(self.rv)
        self.st.addWidget(self.rsv)

        self.lv.go_to_reg.connect(lambda: self.st.setCurrentIndex(1))
        self.lv.go_to_restore.connect(lambda: self.st.setCurrentIndex(2))
        self.rv.go_back.connect(lambda: self.st.setCurrentIndex(0))
        self.rsv.go_back.connect(lambda: self.st.setCurrentIndex(0))
        self.lv.login_success.connect(self.login_success.emit)
        self.lv.go_to_lan.connect(self.go_to_lan_requested.emit)

        l = QVBoxLayout(self); l.addWidget(self.st)