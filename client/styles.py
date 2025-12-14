from PySide6.QtGui import QIcon, QPixmap

# --- ЦВЕТОВАЯ ПАЛИТРА (PREMIUM DARK) ---
BG_MAIN = "#0F172A"       # Глубокий темно-синий (фон приложения)
BG_CARD = "#1E293B"       # Чуть светлее (карточка)
ACCENT_GRADIENT = "qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #8b5cf6)" # Градиент Indigo-Purple
ACCENT_COLOR = "#6366f1"
TEXT_WHITE = "#F8FAFC"
TEXT_GREY = "#94A3B8"
BORDER_INPUT = "#334155"
BORDER_FOCUS = "#8b5cf6"  # Фиолетовая обводка при фокусе

SVG_EYE_OPEN = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M2.45825 12C3.73253 7.94288 7.52281 5 12.0002 5C16.4776 5 20.2678 7.94288 21.5421 12C20.2678 16.0571 16.4776 19 12.0002 19C7.52281 19 3.73253 16.0571 2.45825 12Z" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>"""
SVG_EYE_CLOSED = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 2L22 22" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M6.71277 6.7226C3.66479 8.79527 2.45812 12 2.45812 12C3.7324 16.0571 7.52268 19 12.0001 19C14.5205 19 16.8049 18.0674 18.4901 16.5298" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M9.88281 9.89746C9.52488 10.4571 9.38715 11.2335 9.61036 12.0528C9.97018 13.3737 11.3113 14.1507 12.6323 13.7909C12.8727 13.7254 13.0858 13.6186 13.2687 13.4831" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>"""
SVG_USER = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 11C14.2091 11 16 9.20914 16 7C16 4.79086 14.2091 3 12 3C9.79086 3 8 4.79086 8 7C8 9.20914 9.79086 11 12 11Z" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>"""
SVG_MAIL = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 4H20C21.1 4 22 4.9 22 6V18C22 19.1 21.1 20 20 20H4C2.9 20 2 19.1 2 18V6C2 4.9 2.9 4 4 4Z" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 6L12 13L2 6" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>"""
SVG_LOCK = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M19 11H5C3.89543 11 3 11.8954 3 13V20C3 21.1046 3.89543 22 5 22H19C20.1046 22 21 21.1046 21 20V13C21 11.8954 20.1046 11 19 11Z" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 11V7C7 5.67392 7.52678 4.40215 8.46447 3.46447C9.40215 2.52678 10.6739 2 12 2C13.3261 2 14.5979 2.52678 15.5355 3.46447C16.4732 4.40215 17 5.67392 17 7V11" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

CHECK_ICON = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSI0IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIi8+PC9zdmc+"

def get_icon(svg_data):
    pixmap = QPixmap()
    pixmap.loadFromData(svg_data.encode('utf-8'))
    return QIcon(pixmap)

# Стили для Формы Авторизации
AUTH_STYLES = f"""
    /* Главный фон */
    QWidget#AuthContainer {{ 
        background-color: {BG_MAIN}; 
    }}
    
    /* Карточка (Плашка) */
    QFrame#AuthCard {{ 
        background-color: {BG_CARD}; 
        border: 1px solid #334155;
        border-radius: 24px;
        min-width: 380px;
        max-width: 440px;
    }}
    
    /* Текстовые поля */
    QWidget#FloatingWidget {{ background: transparent; }}
    
    QLabel#FloatingLabel {{
        color: {ACCENT_COLOR};
        font-family: 'Segoe UI', sans-serif;
        font-size: 13px;
        font-weight: 600;
        margin-left: 4px;
        margin-bottom: 2px;
    }}

    QLineEdit {{
        background-color: #0F172A;
        border: 1px solid {BORDER_INPUT};
        border-radius: 12px;
        padding: 0px 15px;
        color: {TEXT_WHITE};
        font-family: 'Segoe UI', sans-serif;
        font-size: 15px;
        selection-background-color: {ACCENT_COLOR};
    }}
    QLineEdit:focus {{
        border: 1px solid {BORDER_FOCUS};
        background-color: #151e32;
    }}

    /* Заголовки */
    QLabel#AppTitle {{ 
        color: {TEXT_WHITE}; 
        font-size: 32px; 
        font-weight: bold; 
        font-family: 'Segoe UI', sans-serif; 
    }}
    
    QLabel#SubTitle {{ 
        color: {TEXT_GREY}; 
        font-size: 15px; 
    }}
    
    QLabel#SmallText {{ 
        color: {TEXT_GREY}; 
        font-size: 13px; 
        font-family: 'Segoe UI'; 
    }}

    /* Главная кнопка (Градиент) */
    QPushButton#PrimaryBtn {{
        background-color: {ACCENT_COLOR}; /* Fallback */
        background-color: {ACCENT_GRADIENT};
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: 700;
        font-size: 16px;
        font-family: 'Segoe UI', sans-serif;
        letter-spacing: 0.5px;
    }}
    QPushButton#PrimaryBtn:hover {{
        margin-top: -2px; /* Легкое поднятие при наведении */
    }}
    QPushButton#PrimaryBtn:pressed {{
        margin-top: 1px;
    }}
    QPushButton#PrimaryBtn:disabled {{
        background-color: {BORDER_INPUT};
        color: {TEXT_GREY};
        margin-top: 0px;
    }}

    /* Второстепенные текстовые кнопки */
    QPushButton#LinkBtn {{
        background: transparent; 
        color: {ACCENT_COLOR}; 
        border: none; 
        font-size: 13px; 
        font-weight: 600; 
        font-family: 'Segoe UI', sans-serif;
    }}
    QPushButton#LinkBtn:hover {{ 
        color: #a78bfa; 
    }}
    
    QPushButton#LinkBtnDanger {{
        background: transparent; 
        color: #ef4444; 
        border: none; 
        font-size: 13px; 
        font-weight: 600; 
        font-family: 'Segoe UI', sans-serif;
    }}

    /* Чекбокс */
    QCheckBox {{
        color: {TEXT_GREY};
        font-size: 14px;
        font-family: 'Segoe UI', sans-serif;
        spacing: 10px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border: 2px solid {BORDER_INPUT};
        border-radius: 6px;
        background: #0F172A;
    }}
    QCheckBox::indicator:hover {{
        border-color: {ACCENT_COLOR};
    }}
    QCheckBox::indicator:checked {{
        background-color: {ACCENT_COLOR};
        border-color: {ACCENT_COLOR};
        image: url('{CHECK_ICON}');
    }}
"""