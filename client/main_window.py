from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PySide6.QtCore import QThread
from client.widgets.auth_forms import AuthPage
from client.widgets.lanchat_page import LanChatWidget, LanSetupWidget, LanWorker
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
        
        self.auth_page = AuthPage()
        self.auth_page.login_success.connect(self.on_login)
        self.auth_page.go_to_lan_requested.connect(self.start_lan_mode)
        
        self.stack.addWidget(self.auth_page)

        self.main_widget = QWidget()
        self.setup_main_ui()
        self.stack.addWidget(self.main_widget)

        self.lan_worker = LanWorker()
        self.lan_setup = LanSetupWidget(self.lan_worker)
        self.lan_setup.back_signal.connect(self.exit_lan_mode)
        self.lan_setup.start_chat_signal.connect(self.show_lan_chat)
        self.stack.addWidget(self.lan_setup)

        self.lan_chat = LanChatWidget(self.lan_worker)
        self.lan_chat.close_chat_signal.connect(self.stop_lan_chat)
        self.stack.addWidget(self.lan_chat)

    def setup_main_ui(self):
        layout = QHBoxLayout(self.main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.sidebar = Sidebar()
        self.sidebar.setObjectName("Sidebar") 
        
        self.content = ContentArea(self.theme_manager)
        
        self.content.logout_requested.connect(self.handle_logout)
        self.content.switch_user_requested.connect(self.on_login)
        
        # Обновляем сайдбар (аватарку) ТОЛЬКО если изменился именно аватар,
        # а не просто текст профиля.
        self.content.user_data_changed.connect(lambda: self.sidebar.reload_avatar())
        
        self.sidebar.btn_profile.clicked.connect(self.content.show_profile)
        self.sidebar.btn_feed.clicked.connect(self.content.show_feed)
        self.sidebar.btn_media.clicked.connect(self.content.show_media)
        self.sidebar.btn_friends.clicked.connect(self.content.show_friends)
        self.sidebar.btn_msg.clicked.connect(self.content.show_messages)
        self.sidebar.btn_settings.clicked.connect(self.content.show_settings)
        
        layout.addWidget(self.sidebar)
        layout.addWidget(self.content)

    def on_login(self, username):
        self.sidebar.set_username(username)
        self.content.set_user(username)
        self.stack.setCurrentIndex(1)
        self.content.show_profile()

    def handle_logout(self):
        self.sidebar.set_username("Guest")
        self.content.set_user("")
        self.stack.setCurrentIndex(0) 

        if hasattr(self.auth_page, 'login_view'):
             self.auth_page.login_view.inp_login.clear()
             self.auth_page.login_view.inp_pass.clear()

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
        # Останавливаем глобальный пул потоков
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().clear()
        QThreadPool.globalInstance().waitForDone(3000)  # Ждем 3 секунды
        
        # Останавливаем LAN worker
        if hasattr(self, 'lan_worker'):
            self.lan_worker.close()
        
        # Останавливаем все потоки в content area
        if hasattr(self, 'content'):
            if hasattr(self.content, 'msg'):
                self.content.msg.stop_all_workers()
            if hasattr(self.content, 'fr'):
                self.content.fr.stop_all_workers()
            if hasattr(self.content, 'mp'):
                self.content.mp.stop_all_workers()
        
        # Останавливаем все потоки в auth page
        if hasattr(self, 'auth_page'):
            # Находим и останавливаем все NetworkWorker потоки
            for thread in self.auth_page.findChildren(QThread):
                if thread.isRunning():
                    thread.quit()
                    thread.wait(1000)
                    if thread.isRunning():
                        thread.terminate()
        
        event.accept()