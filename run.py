import sys
import os
import threading
import uvicorn
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from client.main_window import MainWindow
from client.widgets.theme_manager import ThemeManager

# Подгрузка конфигурации виджетов для изменения API URL на лету
import client.widgets.auth_forms
import client.widgets.settings_page
import client.widgets.friends_page
# !!! ДОБАВЛЯЕМ ИМПОРТ НИЖЕ !!!
import client.widgets.messages_page.network 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Важно для современных Qt приложений
QCoreApplication.setAttribute(Qt.AA_UseOpenGLES)
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

# Порт
PORT = 8001
# При запуске клиента на той же машине, он стучится на локалхост
DEFAULT_API_URL = f"https://localhost:{PORT}"

client.widgets.auth_forms.API_URL = DEFAULT_API_URL
client.widgets.settings_page.API_URL = DEFAULT_API_URL
client.widgets.friends_page.API_URL = DEFAULT_API_URL
# !!! ПРИМЕНЯЕМ НАСТРОЙКУ ТУТ !!!
client.widgets.messages_page.network.API_URL = DEFAULT_API_URL

def start_server_node():
    """
    Запуск серверной части.
    host="0.0.0.0" ОБЯЗАТЕЛЕН для доступности по локальной сети.
    Если поставить 127.0.0.1 - сокеты извне не подключатся.
    """
    try:
        uvicorn.run(
            "app.main:app", 
            host="0.0.0.0", 
            port=PORT,
            log_level="info", 
            ssl_keyfile="key.pem", 
            ssl_certfile="cert.pem"
        )
    except Exception as e:
        logger.critical(f"Server Fail: {e}")
        os._exit(1)

if __name__ == "__main__":
    # Сервер в потоке
    server_t = threading.Thread(target=start_server_node, daemon=True)
    server_t.start()

    # Клиент GUI
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    tm = ThemeManager(app)
    # Передаем TM в главное окно
    w = MainWindow(tm)
    tm.apply_theme()
    w.show()
    
    sys.exit(app.exec())