import socket
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QStackedWidget, QFrame, 
    QMessageBox, QListWidget, QListWidgetItem,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor

# --- ЛОГИКА СОКЕТОВ ---
class LanWorker(QObject):
    msg_received = Signal(str)
    connection_success = Signal()
    connection_lost = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.sock = None
        self.running = False

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Трюк: подключаемся к Google DNS чтобы узнать, какой интерфейс смотрит в мир
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def start_host(self, port=5555):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Разрешаем повторное использование адреса
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('0.0.0.0', int(port)))
            self.sock.listen(1)
            
            t = threading.Thread(target=self._accept_client, daemon=True)
            t.start()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def connect_to_host(self, ip, port=5555):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((ip, int(port)))
            self.sock.settimeout(None)
            self.running = True
            self.connection_success.emit()
            
            t = threading.Thread(target=self._receive_loop, daemon=True)
            t.start()
        except Exception as e:
            self.error_occurred.emit(f"Не удалось подключиться: {e}")

    def _accept_client(self):
        try:
            conn, addr = self.sock.accept()
            self.sock.close() # Закрываем слушающий сокет, работаем только с клиентом
            self.sock = conn
            self.running = True
            self.connection_success.emit()
            self._receive_loop()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _receive_loop(self):
        while self.running and self.sock:
            try:
                data = self.sock.recv(4096)
                if not data: break
                self.msg_received.emit(data.decode('utf-8'))
            except:
                break
        self.running = False
        self.connection_lost.emit("Собеседник отключился")

    def send_message(self, text):
        if self.sock and self.running:
            try:
                self.sock.sendall(text.encode('utf-8'))
            except:
                self.connection_lost.emit("Ошибка отправки")

    def close(self):
        self.running = False
        if self.sock:
            try: self.sock.close()
            except: pass

# --- GUI КОМПОНЕНТЫ ---

class LanSetupWidget(QWidget):
    start_chat_signal = Signal()
    back_signal = Signal()

    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.init_ui()
        self.worker.connection_success.connect(self.on_success)
        self.worker.error_occurred.connect(self.on_error)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Карточка в том же стиле, что и авторизация
        card = QFrame()
        card.setObjectName("AuthCard") # Берет стили из styles.py
        
        # Тень
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40); shadow.setColor(QColor(0,0,0,80)); shadow.setYOffset(10)
        card.setGraphicsEffect(shadow)

        card_l = QVBoxLayout(card)
        card_l.setSpacing(15)
        card_l.setContentsMargins(30,30,30,30)

        # Заголовок
        lbl_t = QLabel("LAN Соединение")
        lbl_t.setObjectName("AppTitle") # Белый, крупный
        lbl_t.setAlignment(Qt.AlignCenter)

        # Выбор режима (Host/Join)
        mode_layout = QHBoxLayout()
        self.btn_host = QPushButton("Создать")
        self.btn_host.setCheckable(True)
        self.btn_host.setChecked(True)
        self.btn_host.setFixedHeight(40)
        self.btn_host.clicked.connect(lambda: self.switch_mode(True))
        
        self.btn_join = QPushButton("Подключиться")
        self.btn_join.setCheckable(True)
        self.btn_join.setFixedHeight(40)
        self.btn_join.clicked.connect(lambda: self.switch_mode(False))
        
        # Стили кнопок переключения (попроще)
        base_style = "border-radius: 8px; font-weight: bold;"
        self.btn_host.setStyleSheet(base_style + "background-color: #3b82f6; color: white;")
        self.btn_join.setStyleSheet(base_style + "background-color: #334155; color: #94a3b8;")
        
        mode_layout.addWidget(self.btn_host)
        mode_layout.addWidget(self.btn_join)

        # Стек вкладок
        self.stack = QStackedWidget()
        
        # Вкладка 1: HOST
        host_w = QWidget()
        h_l = QVBoxLayout(host_w)
        h_l.setContentsMargins(0,10,0,0)
        h_desc = QLabel("Сообщите этот IP собеседнику:")
        h_desc.setStyleSheet("color: #94a3b8;")
        self.inp_my_ip = QLineEdit(self.worker.get_local_ip())
        self.inp_my_ip.setReadOnly(True)
        self.inp_my_ip.setAlignment(Qt.AlignCenter)
        self.inp_my_ip.setStyleSheet("font-size: 20px; font-weight: bold; color: #4ade80; border: 1px solid #334155; border-radius: 8px; padding: 10px; background: #0f172a;")
        
        self.btn_create = QPushButton("Запустить сервер")
        self.btn_create.setObjectName("PrimaryBtn")
        self.btn_create.clicked.connect(self.start_host_action)
        
        h_l.addWidget(h_desc)
        h_l.addWidget(self.inp_my_ip)
        h_l.addSpacing(10)
        h_l.addWidget(self.btn_create)

        # Вкладка 2: CLIENT
        client_w = QWidget()
        c_l = QVBoxLayout(client_w)
        c_l.setContentsMargins(0,10,0,0)
        c_desc = QLabel("Введите IP создателя:")
        c_desc.setStyleSheet("color: #94a3b8;")
        self.inp_target = QLineEdit()
        self.inp_target.setPlaceholderText("Например: 192.168.1.5")
        self.inp_target.setStyleSheet("padding: 10px; color: white; background: #0f172a; border: 1px solid #334155; border-radius: 8px;")
        
        self.btn_connect = QPushButton("Присоединиться")
        self.btn_connect.setObjectName("PrimaryBtn")
        self.btn_connect.clicked.connect(self.start_join_action)
        
        c_l.addWidget(c_desc)
        c_l.addWidget(self.inp_target)
        c_l.addSpacing(10)
        c_l.addWidget(self.btn_connect)

        self.stack.addWidget(host_w)
        self.stack.addWidget(client_w)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #fbbf24; margin-top: 5px;")

        self.btn_back = QPushButton("Вернуться назад")
        self.btn_back.setObjectName("LinkBtn") # Стиль как у ссылки
        self.btn_back.clicked.connect(self.back_signal.emit)

        card_l.addWidget(lbl_t)
        card_l.addLayout(mode_layout)
        card_l.addWidget(self.stack)
        card_l.addWidget(self.lbl_status)
        card_l.addWidget(self.btn_back)

        layout.addWidget(card)

    def switch_mode(self, is_host):
        self.btn_host.setChecked(is_host)
        self.btn_join.setChecked(not is_host)
        if is_host:
            self.stack.setCurrentIndex(0)
            self.btn_host.setStyleSheet("border-radius: 8px; font-weight: bold; background-color: #3b82f6; color: white;")
            self.btn_join.setStyleSheet("border-radius: 8px; font-weight: bold; background-color: #334155; color: #94a3b8;")
        else:
            self.stack.setCurrentIndex(1)
            self.btn_join.setStyleSheet("border-radius: 8px; font-weight: bold; background-color: #3b82f6; color: white;")
            self.btn_host.setStyleSheet("border-radius: 8px; font-weight: bold; background-color: #334155; color: #94a3b8;")

    def start_host_action(self):
        self.btn_create.setEnabled(False)
        self.btn_create.setText("Ожидание...")
        self.lbl_status.setText("Ждем подключение друга...")
        self.worker.start_host()

    def start_join_action(self):
        ip = self.inp_target.text().strip()
        if not ip: return
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("Вход...")
        self.worker.connect_to_host(ip)

    def on_success(self):
        self.btn_create.setEnabled(True); self.btn_create.setText("Запустить сервер")
        self.btn_connect.setEnabled(True); self.btn_connect.setText("Присоединиться")
        self.lbl_status.setText("")
        self.start_chat_signal.emit()

    def on_error(self, err):
        self.btn_create.setEnabled(True); self.btn_create.setText("Запустить сервер")
        self.btn_connect.setEnabled(True); self.btn_connect.setText("Присоединиться")
        self.lbl_status.setText(err)

class LanChatWidget(QWidget):
    close_chat_signal = Signal()
    
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.worker.msg_received.connect(self.on_msg)
        self.worker.connection_lost.connect(self.on_loss)
        
        l = QVBoxLayout(self)
        l.setContentsMargins(0,0,0,0)
        
        # Хедер
        top = QFrame()
        top.setStyleSheet("background: #1e293b; border-bottom: 1px solid #334155;")
        tl = QHBoxLayout(top)
        t_lbl = QLabel("Чат прямой связи (P2P)")
        t_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        t_btn = QPushButton("Отключиться")
        t_btn.setStyleSheet("background: #ef4444; color: white; border-radius: 6px; padding: 5px 15px;")
        t_btn.clicked.connect(self.exit_chat)
        tl.addWidget(t_lbl)
        tl.addStretch()
        tl.addWidget(t_btn)
        
        self.msgs = QListWidget()
        self.msgs.setStyleSheet("background: #0f172a; border: none;")
        
        bot = QFrame()
        bot.setStyleSheet("background: #1e293b; border-top: 1px solid #334155;")
        bl = QHBoxLayout(bot)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Сообщение...")
        self.inp.setStyleSheet("padding: 10px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: white;")
        self.inp.returnPressed.connect(self.send)
        
        bs = QPushButton("➤")
        bs.setFixedSize(40,40)
        bs.clicked.connect(self.send)
        bs.setStyleSheet("border-radius: 20px; background: #6366f1; color: white; font-weight: bold;")
        
        bl.addWidget(self.inp)
        bl.addWidget(bs)
        
        l.addWidget(top)
        l.addWidget(self.msgs)
        l.addWidget(bot)

    def send(self):
        txt = self.inp.text().strip()
        if not txt: return
        self.add_bubble(txt, True)
        self.worker.send_message(txt)
        self.inp.clear()

    def on_msg(self, txt):
        self.add_bubble(txt, False)

    def add_bubble(self, txt, is_me):
        item = QListWidgetItem(self.msgs)
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(10,5,10,5)
        lbl = QLabel(txt)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background: {'#6366f1' if is_me else '#334155'}; 
            color: white; 
            padding: 10px; 
            border-radius: 12px;
            font-size: 14px;
        """)
        lbl.setMaximumWidth(400)
        
        if is_me:
            hl.addStretch()
            hl.addWidget(lbl)
        else:
            hl.addWidget(lbl)
            hl.addStretch()
            
        item.setSizeHint(w.sizeHint())
        self.msgs.setItemWidget(item, w)
        self.msgs.scrollToBottom()

    def exit_chat(self):
        self.worker.close()
        self.close_chat_signal.emit()

    def on_loss(self, reason):
        QMessageBox.information(self, "Конец связи", reason)
        self.close_chat_signal.emit()