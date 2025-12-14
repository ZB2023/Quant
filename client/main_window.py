from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PySide6.QtCore import QTimer, QCoreApplication
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
        
        # Страница авторизации (она постоянна, её не пересоздаем)
        self.auth_page = AuthPage()
        self.auth_page.login_success.connect(self.on_login_start) # Изменили слот
        self.auth_page.go_to_lan_requested.connect(self.start_lan_mode)
        self.stack.addWidget(self.auth_page)

        # Контейнер для основного интерфейса
        # Мы будем очищать его и наполнять заново при входе
        self.main_container = QWidget()
        self.main_layout = QHBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.sidebar = None
        self.content = None
        
        self.stack.addWidget(self.main_container)

        # LAN компоненты (не меняем)
        self.lan_worker = LanWorker()
        self.lan_setup = LanSetupWidget(self.lan_worker)
        self.lan_setup.back_signal.connect(self.exit_lan_mode)
        self.lan_setup.start_chat_signal.connect(self.show_lan_chat)
        self.stack.addWidget(self.lan_setup)

        self.lan_chat = LanChatWidget(self.lan_worker)
        self.lan_chat.close_chat_signal.connect(self.stop_lan_chat)
        self.stack.addWidget(self.lan_chat)

    def on_login_start(self, username):
        # Делаем паузу перед уничтожением мира
        QTimer.singleShot(10, lambda: self._perform_switch(username))
        
    def _perform_switch(self, username):
        # 1. СБРОС СЕТЕВОГО СЛОЯ
        # Это инвалидирует все летящие ответы от сервера. 
        # Даже если ответ придет, он будет проигнорирован и не полезет в удаленный виджет.
        ThreadPoolManager().clear_all_tasks()
        
        # 2. Остановка LAN
        if hasattr(self, 'lan_worker'):
            self.lan_worker.close()

        # 3. МЯГКОЕ УДАЛЕНИЕ UI
        if self.content:
            # Скрываем, чтобы пользователь не видел процесс умирания
            self.content.hide() 
            
            # Останавливаем таймеры, если есть
            if hasattr(self.content, 'msg'): self.content.msg.stop_all_workers()
            if hasattr(self.content, 'fr'): self.content.fr.stop_all_workers()
            
            # Отвязываем от лейаута
            self.main_layout.removeWidget(self.content)
            self.content.setParent(None) # Важный шаг для разрыва связей C++
            self.content.deleteLater()   # Планируем удаление
            self.content = None
        
        if self.sidebar:
            self.sidebar.hide()
            self.main_layout.removeWidget(self.sidebar)
            self.sidebar.setParent(None)
            self.sidebar.deleteLater()
            self.sidebar = None

        # 4. ОЧИСТКА Qt THREAD POOL
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().clear()
        
        # 5. ДАЕМ Qt ВРЕМЯ НА УБОРКУ
        QCoreApplication.processEvents()

        # 6. СОЗДАЕМ НОВЫЙ ИНТЕРФЕЙС
        self.rebuild_main_ui(username)
        self.stack.setCurrentIndex(1)

    def _perform_login(self, username):
        """Жесткая пересборка интерфейса для нового пользователя."""
        
        # 1. Если был старый интерфейс — уничтожаем его
        if self.content:
            try:
                # Пытаемся остановить таймеры внутри (если метод реализован)
                if hasattr(self.content, 'msg') and hasattr(self.content.msg, 'stop_all_workers'):
                    self.content.msg.stop_all_workers()
                if hasattr(self.content, 'fr') and hasattr(self.content.fr, 'stop_all_workers'):
                    self.content.fr.stop_all_workers()
            except:
                pass
            
            # Отвязываем сигналы, чтобы не крашнуло при deleteLater
            try:
                self.content.logout_requested.disconnect()
                self.content.switch_user_requested.disconnect()
            except: 
                pass
            
            self.content.deleteLater()
            self.content = None
        
        if self.sidebar:
            self.sidebar.deleteLater()
            self.sidebar = None
            
        # 2. Очищаем пул потоков (задачи, стоящие в очереди на выполнение)
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().clear()
        
        # Даем время Qt обработать удаление объектов
        QCoreApplication.processEvents()

        # 3. Создаем "чистый" интерфейс с нуля
        self.rebuild_main_ui(username)

        # 4. Переключаем экран
        self.stack.setCurrentIndex(1)
        # Можно сбросить фокус с полей ввода авторизации
        if hasattr(self.auth_page, 'lv'):
            self.auth_page.lv.inp_pass.clear()

    def rebuild_main_ui(self, username):
        """Создает компоненты заново"""
        self.sidebar = Sidebar()
        self.sidebar.set_username(username)
        self.sidebar.setObjectName("Sidebar")
        
        self.content = ContentArea(self.theme_manager)
        
        # Подключаем сигналы
        self.content.logout_requested.connect(self.handle_logout)
        # Здесь мы снова вызываем on_login_start при смене юзера через настройки
        self.content.switch_user_requested.connect(self.on_login_start)
        
        # Обновление аватара в сайдбаре
        self.content.user_data_changed.connect(lambda: self.sidebar.reload_avatar())
        
        # Навигация
        self.sidebar.btn_profile.clicked.connect(self.content.show_profile)
        self.sidebar.btn_feed.clicked.connect(self.content.show_feed)
        self.sidebar.btn_media.clicked.connect(self.content.show_media)
        self.sidebar.btn_friends.clicked.connect(self.content.show_friends)
        self.sidebar.btn_msg.clicked.connect(self.content.show_messages)
        self.sidebar.btn_settings.clicked.connect(self.content.show_settings)
        
        # Добавляем в layout
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content)
        
        # Инициализируем пользователя в контенте
        self.content.set_user(username)
        # Сразу применяем тему, чтобы новые виджеты окрасились
        if self.theme_manager:
            self.theme_manager.apply_theme()
            
    def handle_logout(self):
        # При выходе просто показываем экран логина. 
        # Старые виджеты уничтожим при следующем входе.
        self.stack.setCurrentIndex(0) 

    # --- LAN методы без изменений ---
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
        # Глобальная очистка при закрытии приложения
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().clear()
        
        if hasattr(self, 'lan_worker'):
            self.lan_worker.close()
            
        event.accept()