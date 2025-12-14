from PySide6.QtCore import QObject, Signal

class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        
        # Начальные настройки
        self.current_mode = "dark"
        self.current_accent = "#6366f1"

        # ПАЛИТРЫ
        self.palettes = {
            # === ТЁМНАЯ ТЕМА ===
            "dark": {
                "bg_main": "#0f0f13",
                "bg_sec": "#181820",
                "text_main": "#ffffff",
                "text_sec": "#9ca3af",
                "border": "#2d2d3b",
                "input_bg": "#121217",
                "hover": "rgba(255, 255, 255, 0.08)",
                "active_bg": "rgba(255, 255, 255, 0.1)",
                "selection": "rgba(99, 102, 241, 0.4)",
                # Цвета статусов (яркие для темного фона)
                "status_online": "#4ade80",
                "status_pending": "#818cf8",
                "status_blocked": "#ef4444"
            },
            # === СВЕТЛАЯ ТЕМА ===
            "light": {
                "bg_main": "#f3f4f6",
                "bg_sec": "#ffffff",
                "text_main": "#111827",
                "text_sec": "#6b7280",
                "border": "#e5e7eb",
                "input_bg": "#ffffff",
                "hover": "rgba(0, 0, 0, 0.05)",
                "active_bg": "rgba(0, 0, 0, 0.08)",
                "selection": "rgba(99, 102, 241, 0.2)",
                # Цвета статусов (более темные для светлого фона)
                "status_online": "#16a34a",
                "status_pending": "#4f46e5",
                "status_blocked": "#dc2626"
            },
            # === ВЫСОКАЯ КОНТРАСТНОСТЬ ===
            "high_contrast": {
                "bg_main": "#000000",       
                "bg_sec": "#000000",        
                "text_main": "#ffff00",     
                "text_sec": "#00ff00",      
                "border": "#ffffff",        
                "input_bg": "#000000",      
                "hover": "#1a1a1a",         
                "active_bg": "#333333",     
                "selection": "#ff00ff",
                # Максимальный контраст
                "status_online": "#00ff00",
                "status_pending": "#00ffff",
                "status_blocked": "#ff0000"
            }
        }

    def get_contrast_text_color(self, hex_color):
        try:
            h = hex_color.lstrip('#')
            if len(h) != 6: return "white"
            r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000
            return "black" if yiq >= 140 else "white"
        except:
            return "white"

    def apply_theme(self, mode=None, accent=None):
        if mode: self.current_mode = mode
        if accent: self.current_accent = accent

        p = self.palettes[self.current_mode]
        acc = self.current_accent

        if self.current_mode == "high_contrast":
            border_w = "2px"
            button_bg = "#ffff00"  
            button_text = "black"
            selection_color = p['text_main']
            selection_text = "black"
            # Акцент (заголовки) для контрастной темы
            accent_color = p['text_main']
        else:
            border_w = "1px"
            button_bg = acc
            button_text = self.get_contrast_text_color(acc)
            selection_color = acc
            selection_text = button_text
            # Акцент совпадает с выбранным цветом
            accent_color = acc

        # === ГЕНЕРАЦИЯ СТИЛЕЙ CSS ===
        stylesheet = f"""
            /* --- Глобальные настройки шрифта и фона --- */
            QMainWindow, QWidget {{
                background-color: {p['bg_main']};
                color: {p['text_main']};
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }}

            /* --- САЙДБАР --- */
            QWidget#Sidebar {{
                background-color: {p['bg_sec']};
                border-right: {border_w} solid {p['border']};
            }}
            
            /* Аватар */
            QLabel#Avatar {{
                background-color: {button_bg};
                color: {button_text};
                font-size: 32px; 
                font-weight: bold;
                border-radius: 40px;
                border: {border_w} solid {p['border']};
            }}
            
            /* Имя пользователя */
            QLabel#UsernameLabel {{
                font-size: 18px; 
                font-weight: bold;
                color: {p['text_main']};
                background: transparent;
            }}

            /* --- МЕНЮ НАВИГАЦИИ --- */
            QPushButton#NavBtn {{
                background-color: transparent;
                text-align: left;
                padding-left: 20px;
                border: none;
                color: {p['text_sec']};
                font-size: 15px;
                font-weight: 500;
                border-radius: 10px;
                margin: 2px 10px;
                border: 1px solid transparent; 
            }}
            QPushButton#NavBtn:hover {{
                background-color: {p['hover']};
                color: {p['text_main']};
            }}
            QPushButton#NavBtn:checked, QPushButton#NavBtn:pressed {{
                background-color: {p['active_bg']};
                color: {p['text_main']};
                font-weight: bold;
                border: {border_w} solid {button_bg};
            }}

            /* --- ОБЩИЕ ЭЛЕМЕНТЫ --- */
            QFrame, QLabel {{ border: none; background: transparent; }}
            
            /* Карточки */
            QFrame#AuthCard, QGroupBox {{
                background-color: {p['bg_sec']};
                border: {border_w} solid {p['border']};
                border-radius: 16px;
                color: {p['text_main']};
            }}
            
            /* Поле ввода сообщения (нижняя панель) */
            QFrame#MessageInputArea {{
                background-color: {p['bg_sec']}; 
                border-top: {border_w} solid {p['border']};
            }}

            /* Заголовки */
            QLabel#Header, QGroupBox::title {{
                color: {p['text_main']};
                font-weight: bold;
            }}
            
            QLabel#SubTitle {{
                color: {p['text_sec']};
                font-size: 13px;
            }}

            /* --- НОВЫЕ СТИЛИ ДЛЯ СТАТУСОВ --- */
            QLabel#StatusOnline {{
                color: {p['status_online']};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#StatusPending {{
                color: {p['status_pending']};
                font-size: 12px;
                font-weight: bold;
            }}
            QLabel#StatusBlocked {{
                color: {p['status_blocked']};
                font-size: 12px;
                font-weight: 600;
            }}
            
            /* Заголовок Секции (в Друзьях) */
            QLabel#SectionTitle {{
                color: {accent_color};
                font-size: 13px;
                font-weight: bold;
                text-transform: uppercase;
                margin-top: 15px; 
                margin-bottom: 5px;
            }}

            /* --- ПОЛЯ ВВОДА --- */
            QLineEdit, QTextEdit {{
                background-color: {p['input_bg']};
                border: {border_w} solid {p['border']};
                border-radius: 10px;
                padding: 10px;
                color: {p['text_main']};
                selection-background-color: {selection_color};
                selection-color: {selection_text};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: {border_w} solid {button_bg};
            }}

            /* --- КНОПКИ --- */
            QPushButton#PrimaryBtn, QPushButton[class="primary"] {{
                background-color: {button_bg};
                color: {button_text}; 
                border: {border_w} solid {p['border']};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {button_bg};
                border: {border_w} solid {p['text_main']};
            }}

            QPushButton#ColorBtn {{
                border-radius: 15px;
                border: 2px solid {p['border']}; 
            }}
            QPushButton#ColorBtn:checked {{
                border: 2px solid {p['text_main']};
            }}
            
            QPushButton#ThemeCard {{
                background-color: {p['input_bg']};
                border: {border_w} solid {p['border']};
                border-radius: 12px;
                color: {p['text_main']};
            }}
            QPushButton#ThemeCard:checked {{
                border: 2px solid {button_bg};
                background-color: {p['hover']};
            }}
            
            QPushButton {{ border-radius: 8px; }}

            /* Скроллбар */
            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0px; }}
            QScrollBar::handle:vertical {{ 
                background: {p['border']}; 
                min-height: 30px; 
                border-radius: 4px; 
            }}
            QScrollBar::handle:vertical:hover {{ background: {button_bg}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """

        self.app.setStyleSheet(stylesheet)
        self.theme_changed.emit(stylesheet)