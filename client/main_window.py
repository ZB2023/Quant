from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PySide6.QtCore import QTimer, QCoreApplication, QThreadPool
from client.widgets.auth_forms import AuthPage
from client.widgets.lanchat_page import LanChatWidget, LanSetupWidget, LanWorker
from client.widgets.messages_page.network import ThreadPoolManager
from client.widgets.sidebar import Sidebar
from client.widgets.content_area import ContentArea

class MainWindow(QMainWindow):
    def __init__(self, theme_manager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setWindowTitle("Quant Desktop | Secure Messenger")
        self.resize(1100, 750)
        
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Страница авторизации (индекс 0)
        self.auth_page = AuthPage()
        # ВАЖНО: При входе делаем паузу, чтобы предыдущий контекст успел умереть
        self.auth_page.login_success.connect(lambda u: QTimer.singleShot(10, lambda: self.on_login_start(u)))
        self.auth_page.go_to_lan_requested.connect(self.start_lan_mode)
        self.stack.addWidget(self.auth_page)

        # Контейнер основного приложения (индекс 1)
        self.main_container = QWidget()
        self.main_layout = QHBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.sidebar = None
        self.content = None
        self.stack.addWidget(self.main_container)

        # LAN (индекс 2 и 3)
        self.lan_worker = LanWorker()
        self.lan_setup = LanSetupWidget(self.lan_worker)
        self.lan_setup.back_signal.connect(self.exit_lan_mode)
        self.lan_setup.start_chat_signal.connect(self.show_lan_chat)
        self.stack.addWidget(self.lan_setup)

        self.lan_chat = LanChatWidget(self.lan_worker)
        self.lan_chat.close_chat_signal.connect(self.stop_lan_chat)
        self.stack.addWidget(self.lan_chat)

    def on_login_start(self, username):
        """Вход пользователя: сначала зачистка, потом создание."""
        self.auth_page.setEnabled(False) # Блокируем, чтобы не накликовали
        self._destroy_session()          # Полное уничтожение прошлого
        self.rebuild_main_ui(username)   # Создание нового
        self.stack.setCurrentIndex(1)
        
        if hasattr(self.auth_page, 'lv'):
            self.auth_page.lv.inp_pass.clear()
        self.auth_page.setEnabled(True)

    def handle_logout(self):
        """Выход пользователя: полное уничтожение и переход на логин."""
        self._destroy_session()
        
        # Сброс сохранения пароля в конфиге
        from PySide6.QtCore import QSettings
        s = QSettings("QuantProject", "QuantDesktop")
        s.setValue("remember", "false")
        s.remove("login")
        s.remove("password")
        if hasattr(self.auth_page, 'lv'):
            self.auth_page.lv.chk_remember.setChecked(False)

        self.stack.setCurrentIndex(0)

    def _destroy_session(self):
        """Единый метод тотальной зачистки интерфейса и потоков."""
        
        # 1. Отменяем сетевые задачи чата
        ThreadPoolManager().clear_all_tasks()
        
        # 2. Чистим глобальный пул Qt (Runnable)
        QThreadPool.globalInstance().clear()
        
        # 3. LAN
        if hasattr(self, 'lan_worker'):
            self.lan_worker.close()

        # 4. Убиваем КОНТЕНТ (ContentArea)
        if self.content:
            self.content.hide()
            
            # Отключаем сигналы, чтобы не дергался MainWindow
            try: self.content.disconnect()
            except: pass
            
            # Останавливаем таймеры и воркеров внутри страниц
            self._safe_stop(self.content.msg, 'stop_all_workers')
            self._safe_stop(self.content.fr, 'stop_all_workers')
            self._safe_stop(self.content.mp, 'stop_all_workers')
            
            # Помечаем виджеты "мертвыми", чтобы QRunnable не трогали их
            if hasattr(self.content.pp, 'prof'): self.content.pp.prof._is_alive = False
            if hasattr(self.content.fr, '_is_alive'): self.content.fr._is_alive = False

            # Удаляем физически
            self.main_layout.removeWidget(self.content)
            self.content.setParent(None)
            self.content.deleteLater()
            self.content = None

        # 5. Убиваем САЙДБАР (Sidebar)
        if self.sidebar:
            self.sidebar.hide()
            self.sidebar._is_alive = False # Флаг смерти для потока аватара
            
            try: self.sidebar.disconnect()
            except: pass
            
            self.main_layout.removeWidget(self.sidebar)
            self.sidebar.setParent(None)
            self.sidebar.deleteLater()
            self.sidebar = None
        
        # 6. Прокручиваем цикл событий, чтобы Qt удалил объекты из памяти прямо сейчас
        QCoreApplication.processEvents()

    def _safe_stop(self, obj, method_name):
        """Пытается вызвать метод остановки, если объект существует."""
        try:
            if hasattr(obj, method_name):
                getattr(obj, method_name)()
        except:
            pass

    def rebuild_main_ui(self, username):
        """Сборка интерфейса."""
        self.sidebar = Sidebar()
        self.sidebar.set_username(username)
        
        self.content = ContentArea(self.theme_manager)
        
        self.content.logout_requested.connect(self.handle_logout)
        # При смене пользователя через настройки используем _switch_proxy, 
        # чтобы разорвать стек вызова через таймер
        self.content.switch_user_requested.connect(
            lambda u: QTimer.singleShot(0, lambda: self.on_login_start(u))
        )
        
        self.content.user_data_changed.connect(lambda: self.sidebar.reload_avatar())
        
        self.sidebar.btn_profile.clicked.connect(self.content.show_profile)
        self.sidebar.btn_feed.clicked.connect(self.content.show_feed)
        self.sidebar.btn_media.clicked.connect(self.content.show_media)
        self.sidebar.btn_friends.clicked.connect(self.content.show_friends)
        self.sidebar.btn_msg.clicked.connect(self.content.show_messages)
        self.sidebar.btn_settings.clicked.connect(self.content.show_settings)
        
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content)
        
        self.content.set_user(username)
        if self.theme_manager:
            self.theme_manager.apply_theme()

    def start_lan_mode(self):
        self.lan_worker.close() 
        self.stack.setCurrentIndex(2)

    def exit_lan_mode(self):
        self.lan_worker.close()
        self.stack.setCurrentIndex(0) 

    def show_lan_chat(self):
        self.stack.setCurrentIndex(3)
        self.lan_chat.msgs.clear()

    def stop_lan_chat(self):
        self.lan_worker.close()
        self.stack.setCurrentIndex(2)
        
    def closeEvent(self, event):
        self._destroy_session()
        event.accept()