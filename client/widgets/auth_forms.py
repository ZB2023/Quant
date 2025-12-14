import requests
import urllib3
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QStackedWidget, QFrame, QMessageBox, 
    QCheckBox, QSizePolicy, QGraphicsOpacityEffect, QDialog,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QParallelAnimationGroup, QThread, QObject, QSize
from PySide6.QtGui import QAction, QColor

import client.widgets.friends_page
import client.widgets.settings_page

from client.styles import (
    AUTH_STYLES, get_icon, 
    SVG_USER, SVG_MAIL, SVG_LOCK, 
    SVG_EYE_OPEN, SVG_EYE_CLOSED
)

print("--- [LOAD] Loading Auth Forms Correctly ---")

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
    # Пробрасываем изменения в остальные модули
    client.widgets.dialogs.API_URL = new_url
    client.widgets.friends_page.API_URL = new_url
    client.widgets.settings_page.API_URL = new_url
    return API_URL

# --- ПОТОКИ ---
class NetworkWorker(QObject):
    finished = Signal(dict)
    
    def __init__(self, task_type, url, data=None):  # Убрать parent=None
        super().__init__()  # Не передавать parent в QObject
        self.task_type = task_type
        self.url = url
        self.data = data

    def run(self):
        res = {"success": False, "msg": "", "code": 0}
        try:
            if self.task_type == "ping":
                # Тайм-аут поменьше, чтобы не висело вечно
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

# --- КРАСИВЫЙ INPUT ---
class InnerEdit(QLineEdit):
    focus_in = Signal()
    focus_out = Signal()
    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.focus_in.emit()
    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.focus_out.emit()

class QuantInput(QWidget):
    def __init__(self, icon_svg, alias_text, hint_text, is_password=False):
        super().__init__()
        self.setObjectName("FloatingWidget")
        self.alias_text = alias_text
        self.hint_text = hint_text
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        
        self.lbl_title = QLabel(self.alias_text)
        self.lbl_title.setObjectName("FloatingLabel")
        self.lbl_title.setFixedHeight(0)
        self.lbl_title.setGraphicsEffect(QGraphicsOpacityEffect(self))
        self.lbl_title.graphicsEffect().setOpacity(0)
        
        self.inp = InnerEdit()
        self.inp.setPlaceholderText(self.alias_text)
        self.inp.setFixedHeight(50)
        self.inp.focus_in.connect(self.animate_focus_in)
        self.inp.focus_out.connect(self.animate_focus_out)
        
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
            
        self.layout.addWidget(self.lbl_title)
        self.layout.addWidget(self.inp)

    def toggle_visibility(self):
        if self.inp.echoMode() == QLineEdit.Password:
            self.inp.setEchoMode(QLineEdit.Normal)
            self.toggle_action.setIcon(self.icon_open)
        else:
            self.inp.setEchoMode(QLineEdit.Password)
            self.toggle_action.setIcon(self.icon_closed)

    def text(self): return self.inp.text()
    def setFocus(self): self.inp.setFocus()
    def clear(self): self.inp.clear()

    def animate_focus_in(self):
        self.inp.setPlaceholderText(self.hint_text)
        self.anim_group = QParallelAnimationGroup()
        a_height = QPropertyAnimation(self.lbl_title, b"minimumHeight")
        a_height.setDuration(150); a_height.setStartValue(0); a_height.setEndValue(20)
        a_opacity = QPropertyAnimation(self.lbl_title.graphicsEffect(), b"opacity")
        a_opacity.setDuration(200); a_opacity.setStartValue(0); a_opacity.setEndValue(1)
        self.anim_group.addAnimation(a_height); self.anim_group.addAnimation(a_opacity)
        self.anim_group.start()
        self.lbl_title.setFixedHeight(20)

    def animate_focus_out(self):
        if self.inp.text(): return
        self.inp.setPlaceholderText(self.alias_text)
        self.anim_group = QParallelAnimationGroup()
        a_height = QPropertyAnimation(self.lbl_title, b"minimumHeight")
        a_height.setDuration(150); a_height.setStartValue(20); a_height.setEndValue(0)
        a_opacity = QPropertyAnimation(self.lbl_title.graphicsEffect(), b"opacity")
        a_opacity.setDuration(150); a_opacity.setStartValue(1); a_opacity.setEndValue(0)
        self.anim_group.addAnimation(a_height); self.anim_group.addAnimation(a_opacity)
        self.anim_group.start()

# --- ФОРМА НАСТРОЙКИ СЕРВЕРА ---
class ServerConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки соединения")
        self.setFixedSize(360, 240)
        # Отдельные стили для диалога, чтобы он выглядел красиво
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
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_head = QLabel("IP-адрес сервера")
        lbl_head.setStyleSheet("font-size: 18px; font-weight: 700; color: white;")
        layout.addWidget(lbl_head)
        
        lbl_info = QLabel("Укажите адрес сервера для проверки соединения:")
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        self.inp_url = QLineEdit()
        # Вырезаем https, чтобы юзеру было удобнее
        clean_ip = API_URL.replace("https://", "").replace(":8001", "")
        self.inp_url.setText(clean_ip)
        layout.addWidget(self.inp_url)

        self.status_bar = QLabel("")
        self.status_bar.setStyleSheet("font-size: 12px; margin-top: 5px;")
        layout.addWidget(self.status_bar)

        self.btn_check = QPushButton("Проверить и Сохранить")
        self.btn_check.setCursor(Qt.PointingHandCursor)
        self.btn_check.clicked.connect(self.start_check)
        layout.addWidget(self.btn_check)

        self.thread = None

    def start_check(self):
        raw = self.inp_url.text().strip()
        if not raw: raw = "localhost"
        
        full_url = update_global_api_url(raw)
        
        # ВИЗУАЛЬНАЯ РЕАКЦИЯ - Сразу меняем текст
        self.btn_check.setEnabled(False)
        self.btn_check.setText("Проверка соединения...")
        self.status_bar.setText(f"Подключение к {full_url}...")
        self.status_bar.setStyleSheet("color: #fbbf24;") # Желтый
        
        self.thread = QThread()
        self.worker = NetworkWorker("ping", full_url)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_check_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_check_finished(self, res):
        self.btn_check.setEnabled(True)
        self.btn_check.setText("Проверить и Сохранить")
        
        if res["success"]:
            self.status_bar.setStyleSheet("color: #4ade80; font-weight: bold;") # Зеленый
            self.status_bar.setText("✓ Сервер доступен. Настройки сохранены.")
            # Даем юзеру увидеть галочку полсекунды, можно сразу закрыть
            # но лучше пусть нажмет крестик или сама закроется.
            # Для надежности:
            QMessageBox.information(self, "Успешно", "Соединение установлено!\nНастройки применены.")
            self.accept()
        else:
            self.status_bar.setStyleSheet("color: #f87171;") # Красный
            err = res["msg"] if res["msg"] else f"Ошибка HTTP: {res['code']}"
            self.status_bar.setText(f"Ошибка: {err}")

# --- КАРТОЧКА ВХОДА (LOGIN) ---
class LoginView(QWidget):
    login_success = Signal(str)
    go_to_reg = Signal()
    go_to_restore = Signal() 
    go_to_lan = Signal()

    def __init__(self):
        super().__init__()
        # Основной вертикальный контейнер для центрирования карточки на экране
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        
        self.card = QFrame()
        self.card.setObjectName("AuthCard")
        
        # Тень (без изменений)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setSpacing(15)
        layout.setContentsMargins(40, 40, 40, 40)

        # Лого / Заголовок (уже по центру, всё ок)
        title = QLabel("Quant Desktop")
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Войдите в аккаунт")
        subtitle.setObjectName("SubTitle")
        subtitle.setAlignment(Qt.AlignCenter)

        # Поля (без изменений)
        self.inp_login = QuantInput(SVG_USER, "Логин", "Ваше имя пользователя")
        self.inp_pass = QuantInput(SVG_LOCK, "Пароль", "••••••", is_password=True)
        
        # Чекбокс "Запомнить меня"
        # -----------------------------------------------
        # ИСПРАВЛЕНИЕ: Выравниваем чекбокс по центру, или оставляем аккуратно слева
        # Здесь лучше оставить слева или добавить отступы. Но, допустим, оставим как есть,
        # так как это стандарт для форм.
        self.chk_remember = QCheckBox("Запомнить меня")
        
        # Кнопка входа (без изменений)
        self.btn_enter = QPushButton("Войти в систему")
        self.btn_enter.setObjectName("PrimaryBtn")
        self.btn_enter.setFixedHeight(50)
        self.btn_enter.setCursor(Qt.PointingHandCursor)
        self.btn_enter.clicked.connect(self.do_login)

        # Ссылки снизу (Нет аккаунта?)
        # -----------------------------------------------
        # ИСПРАВЛЕНИЕ: Центрируем эту строку (было выровнено влево)
        link_area = QHBoxLayout()
        link_area.addStretch() # <--- Добавили пружину слева
        link_area.addWidget(QLabel("Нет аккаунта?", objectName="SmallText"))
        self.btn_reg = QPushButton("Создать аккаунт")
        self.btn_reg.setObjectName("LinkBtn")
        self.btn_reg.setCursor(Qt.PointingHandCursor)
        self.btn_reg.clicked.connect(self.go_to_reg.emit)
        link_area.addWidget(self.btn_reg)
        link_area.addStretch() # <--- Добавили пружину справа (теперь это строго по центру)

        # Футер (Настройки / LAN)
        # -----------------------------------------------
        # ИСПРАВЛЕНИЕ: Делаем горизонтальным (было QVBoxLayout -> стало QHBoxLayout)
        # Убираем лишние margin-top в стилях, выравниваем в одну строку
        footer_layout = QHBoxLayout() 
        footer_layout.setSpacing(20) # Отступ между ссылками
        
        self.btn_lan = QPushButton("📡 P2P Чат") # Сократили текст для аккуратности
        self.btn_lan.setObjectName("LinkBtn")
        self.btn_lan.setStyleSheet("color: #4ade80; font-size: 13px;") 
        self.btn_lan.setCursor(Qt.PointingHandCursor)
        self.btn_lan.clicked.connect(self.handle_lan_click)

        self.btn_settings = QPushButton("⚙ Подключение") # Сократили текст
        self.btn_settings.setObjectName("LinkBtn")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setStyleSheet("color: #94a3b8; font-size: 13px;")
        self.btn_settings.clicked.connect(self.open_settings)
        
        # Добавляем кнопки в горизонтальный слой и центрируем блок пружинами
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_lan)
        footer_layout.addWidget(QLabel("|", styleSheet="color: #334155;")) # Разделитель для красоты
        footer_layout.addWidget(self.btn_settings)
        footer_layout.addStretch()

        # Сборка всего вместе
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(15)
        layout.addWidget(self.inp_login)
        layout.addWidget(self.inp_pass)
        layout.addWidget(self.chk_remember)
        layout.addSpacing(10)
        layout.addWidget(self.btn_enter)
        layout.addSpacing(5) # Небольшой отступ перед ссылками
        layout.addLayout(link_area)
        layout.addSpacing(15) # Отступ перед футером
        layout.addLayout(footer_layout)

        main_layout.addWidget(self.card)

    def handle_lan_click(self):
        print("[DEBUG] LAN Button Clicked in LoginView")
        self.go_to_lan.emit()

    def open_settings(self):
        d = ServerConfigDialog(self)
        d.exec()

    def do_login(self):
        u = self.inp_login.text().strip()
        p = self.inp_pass.text().strip()
        if not u or not p: 
            return # Можно добавить анимацию тряски

        self.btn_enter.setEnabled(False)
        self.btn_enter.setText("Подключение...")
        
        self.thread = QThread()
        self.worker = NetworkWorker("login", API_URL, {"login": u, "pw": p})
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_login_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_login_finished(self, res):
        self.btn_enter.setEnabled(True)
        self.btn_enter.setText("Войти в систему")
        
        if res["success"]:
            self.login_success.emit(self.inp_login.text())
        elif res["code"] == 401:
            QMessageBox.warning(self, "Ошибка входа", "Неверный логин или пароль")
        else:
            QMessageBox.critical(self, "Ошибка сети", f"Сервер недоступен ({API_URL})")

# --- КАРТОЧКА РЕГИСТРАЦИИ (REG) ---
class RegisterView(QWidget):
    go_back = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.card = QFrame()
        self.card.setObjectName("AuthCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40); shadow.setColor(QColor(0,0,0,80)); shadow.setYOffset(10)
        self.card.setGraphicsEffect(shadow)

        l = QVBoxLayout(self.card)
        l.setSpacing(12)
        l.setContentsMargins(40, 40, 40, 40)
        
        title = QLabel("Создание аккаунта")
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignCenter)
        
        self.inp_login = QuantInput(SVG_USER, "Логин", "User")
        self.inp_mail = QuantInput(SVG_MAIL, "Email", "mail@site.com")
        self.inp_pw = QuantInput(SVG_LOCK, "Пароль", "••••••", True)
        self.inp_pw2 = QuantInput(SVG_LOCK, "Повтор пароля", "••••••", True)
        
        self.btn_reg = QPushButton("Зарегистрироваться")
        self.btn_reg.setObjectName("PrimaryBtn")
        self.btn_reg.setFixedHeight(50)
        self.btn_reg.setCursor(Qt.PointingHandCursor)
        self.btn_reg.clicked.connect(self.do_reg)
        
        self.btn_back = QPushButton("Уже есть аккаунт? Войти")
        self.btn_back.setObjectName("LinkBtn")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self.go_back.emit)

        l.addWidget(title)
        l.addSpacing(10)
        l.addWidget(self.inp_login)
        l.addWidget(self.inp_mail)
        l.addWidget(self.inp_pw)
        l.addWidget(self.inp_pw2)
        l.addSpacing(10)
        l.addWidget(self.btn_reg)
        l.addWidget(self.btn_back)
        
        layout.addWidget(self.card)

    def do_reg(self):
        if self.inp_pw.text() != self.inp_pw2.text():
            QMessageBox.warning(self, "Пароль", "Пароли не совпадают!")
            return
        
        data = {
            "login": self.inp_login.text(),
            "email": self.inp_mail.text(),
            "pw": self.inp_pw.text()
        }
        self.btn_reg.setText("Регистрация...")
        self.btn_reg.setEnabled(False)
        
        self.thread = QThread()
        self.worker = NetworkWorker("register", API_URL, data)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_reg_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_reg_finished(self, res):
        self.btn_reg.setEnabled(True)
        self.btn_reg.setText("Зарегистрироваться")
        if res["success"]:
            QMessageBox.information(self, "Успешно", "Аккаунт создан! Теперь вы можете войти.")
            self.go_back.emit()
        else:
            QMessageBox.warning(self, "Ошибка", f"Сбой регистрации.\n{res['msg']}")

# --- КЛАСС ВОССТАНОВЛЕНИЯ (ЗАГЛУШКА) ---
class RestoreView(QWidget):
    go_back = Signal()
    def __init__(self):
        super().__init__()
        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignCenter)
        card = QFrame(objectName="AuthCard")
        cl = QVBoxLayout(card); cl.setContentsMargins(40,40,40,40)
        cl.addWidget(QLabel("Восстановление пока недоступно", objectName="SubTitle"))
        b = QPushButton("Назад", clicked=self.go_back.emit, objectName="LinkBtn")
        cl.addWidget(b)
        l.addWidget(card)

# --- ГЛАВНЫЙ ВИДЖЕТ АВТОРИЗАЦИИ ---
class AuthPage(QWidget):
    login_success = Signal(str)
    go_to_lan_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("AuthContainer")
        self.setStyleSheet(AUTH_STYLES)
        
        self.stack = QStackedWidget()
        
        self.login_view = LoginView()
        self.reg_view = RegisterView()
        self.rest_view = RestoreView()
        
        self.stack.addWidget(self.login_view)
        self.stack.addWidget(self.reg_view)
        self.stack.addWidget(self.rest_view)
        
        # Навигация внутри авторизации
        self.login_view.go_to_reg.connect(lambda: self.stack.setCurrentIndex(1))
        self.login_view.go_to_restore.connect(lambda: self.stack.setCurrentIndex(2))
        
        self.reg_view.go_back.connect(lambda: self.stack.setCurrentIndex(0))
        self.rest_view.go_back.connect(lambda: self.stack.setCurrentIndex(0))
        
        # === ВАЖНЕЙШАЯ СВЯЗКА ДЛЯ РАБОТЫ КНОПОК ===
        self.login_view.login_success.connect(self.login_success.emit)
        
        # Прямая связь: Нажали кнопку LAN -> Отправляем сигнал "хочу LAN" наружу
        self.login_view.go_to_lan.connect(self.on_lan_click)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    def on_lan_click(self):
        print("[DEBUG] AuthPage received LAN signal. Emitting to Main...")
        self.go_to_lan_requested.emit()