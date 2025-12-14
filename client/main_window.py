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
        
        # Основной стек: 
        # 0: Авторизация
        # 1: Основной интерфейс (Sidebar + Content)
        # 2: LAN Setup
        # 3: LAN Chat
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Страница авторизации (постоянная)
        self.auth_page = AuthPage()
        # ВАЖНО: При смене юзера используем отложенный переход, чтобы разорвать стек вызовов
        self.auth_page.login_success.connect(lambda u: QTimer.singleShot(50, lambda: self.on_login_start(u)))
        self.auth_page.go_to_lan_requested.connect(self.start_lan_mode)
        self.stack.addWidget(self.auth_page)

        # Контейнер для основного интерфейса
        self.main_container = QWidget()
        self.main_layout = QHBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.sidebar = None
        self.content = None
        
        self.stack.addWidget(self.main_container)

        # LAN компоненты
        self.lan_worker = LanWorker()
        self.lan_setup = LanSetupWidget(self.lan_worker)
        self.lan_setup.back_signal.connect(self.exit_lan_mode)
        self.lan_setup.start_chat_signal.connect(self.show_lan_chat)
        self.stack.addWidget(self.lan_setup)

        self.lan_chat = LanChatWidget(self.lan_worker)
        self.lan_chat.close_chat_signal.connect(self.stop_lan_chat)
        self.stack.addWidget(self.lan_chat)

    def on_login_start(self, username):
        """Слот, принимающий сигнал о входе."""
        # Блокируем интерфейс, пока идет перестроение, чтобы юзер не нажал лишнего
        if self.auth_page:
            self.auth_page.setEnabled(False)
            
        # Даем текущим событиям завершиться, затем переключаем
        QTimer.singleShot(50, lambda: self._perform_switch(username))
        
    def _perform_switch(self, username):
        """Безопасное переключение контекста."""
        
        # 1. Останавливаем старый LAN Worker
        if hasattr(self, 'lan_worker'):
            self.lan_worker.close()

        # 2. Остановка менеджера задач чатов
        ThreadPoolManager().clear_all_tasks()
        
        # 3. Убиваем ContentArea
        if self.content:
            self.content.hide()
            
            # (A) Отключаем верхнеуровневые сигналы
            try:
                self.content.disconnect()
            except:
                pass

            # (B) Пытаемся остановить внутренних воркеров
            # Обратите внимание: добавляем _is_alive=False принудительно, если есть атрибут
            if hasattr(self.content.pp, 'prof'):
                 self.content.pp.prof._is_alive = False

            if hasattr(self.content, 'msg'): 
                self.content.msg.stop_all_workers()
                
            if hasattr(self.content, 'fr'): 
                self.content.fr.stop_all_workers()

            if hasattr(self.content, 'mp'):
                self.content.mp.stop_all_workers() # Добавленный метод

            # (C) Удаление
            self.main_layout.removeWidget(self.content)
            self.content.setParent(None)
            self.content.deleteLater()
            self.content = None
        
        # 4. Убиваем Sidebar
        if self.sidebar:
            self.sidebar._is_alive = False # Флаг защиты для сайдбара
            try: self.sidebar.disconnect() 
            except: pass
            
            self.sidebar.hide()
            self.main_layout.removeWidget(self.sidebar)
            self.sidebar.setParent(None)
            self.sidebar.deleteLater()
            self.sidebar = None

        # 5. Чистка пула потоков
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().clear()
        
        # 6. Даем время на сборку мусора Qt
        QCoreApplication.processEvents()

        # 7. Строим новый мир
        self.rebuild_main_ui(username)
        self.stack.setCurrentIndex(1)
        
        if hasattr(self.auth_page, 'lv'):
            self.auth_page.lv.inp_pass.clear()
        self.auth_page.setEnabled(True)

    def rebuild_main_ui(self, username):
        """Создает компоненты с нуля."""
        self.sidebar = Sidebar()
        self.sidebar.set_username(username)
        
        self.content = ContentArea(self.theme_manager)
        
        # Подключаем сигналы выхода/смены пользователя
        self.content.logout_requested.connect(self.handle_logout)
        
        # Смена пользователя: ВАЖНО использовать отложенный вызов,
        # чтобы старый диалог успел закрыться до того, как мы уничтожим ContentArea
        self.content.switch_user_requested.connect(self.on_login_start)
        
        # Связываем Сайдбар и Контент
        self.content.user_data_changed.connect(lambda: self.sidebar.reload_avatar())
        
        self.sidebar.btn_profile.clicked.connect(self.content.show_profile)
        self.sidebar.btn_feed.clicked.connect(self.content.show_feed)
        self.sidebar.btn_media.clicked.connect(self.content.show_media)
        self.sidebar.btn_friends.clicked.connect(self.content.show_friends)
        self.sidebar.btn_msg.clicked.connect(self.content.show_messages)
        self.sidebar.btn_settings.clicked.connect(self.content.show_settings)
        
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content)
        
        # Загружаем данные пользователя
        self.content.set_user(username)
        
        # Применяем тему
        if self.theme_manager:
            self.theme_manager.apply_theme()
            
    def handle_logout(self):
        """
        При выходе из аккаунта (Log out) - не уничтожаем мир сразу.
        Просто переключаем экран. Уничтожение старого произойдет 
        в момент Входа следующего пользователя.
        """
        # Сброс пароля в GUI, если он там остался
        if hasattr(self.auth_page, 'lv'):
            self.auth_page.lv.inp_pass.clear()
            self.auth_page.lv.chk_remember.setChecked(False)
            
        # Очистка настроек авторизации (чтобы автологин не сработал снова)
        from PySide6.QtCore import QSettings
        s = QSettings("QuantProject", "QuantDesktop")
        s.setValue("remember", "false")
        s.remove("login")
        s.remove("password")
            
        self.stack.setCurrentIndex(0)

    # --- LAN методы ---
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
        """Глобальная очистка при закрытии окна."""
        QThreadPool.globalInstance().clear()
        
        if self.content:
            try:
                self.content.msg.stop_all_workers()
                self.content.fr.stop_all_workers()
            except: pass
            
        if hasattr(self, 'lan_worker'):
            self.lan_worker.close()
            
        event.accept()