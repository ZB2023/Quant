import time
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFrame, QScrollArea,
    QGridLayout, QPushButton, QWidget, QApplication
)
from PySide6.QtCore import Qt, QPointF, Signal, QRectF, QSize, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QAction, QPalette

class OverlayCloseBtn(QPushButton):
    """
    Круглая кнопка с крестиком для закрытия поверх изображения.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        
    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)
        
    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Полупрозрачный фон (краснеет при наведении)
        if self._hover:
            col = QColor(220, 38, 38, 200) # Красный
        else:
            col = QColor(0, 0, 0, 100) # Темный
            
        painter.setBrush(col)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())
        
        # Белый крестик
        painter.setPen(QPen(Qt.white, 2.5))
        m = 12
        painter.drawLine(m, m, self.width()-m, self.height()-m)
        painter.drawLine(self.width()-m, m, m, self.height()-m)

class HybridGalleryOverlay(QDialog):
    """
    Полноэкранный просмотр изображений.
    - Колесико: зум.
    - ЛКМ по картинке: перемещение картинки.
    - ЛКМ по фону: перемещение окна (если оно не на весь экран).
    """
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Пытаемся развернуть на весь экран родителя или монитора
        if parent and parent.window():
            sz = parent.window().size()
            self.resize(sz)
            # Центрируем относительно родителя
            geom = parent.window().frameGeometry()
            self.move(geom.topLeft())
        else:
            self.showMaximized()
            
        self.pixmap = pixmap
        self.scale_factor = 1.0
        self.offset = QPointF(0, 0)
        
        self.is_dragging_image = False
        self.is_dragging_window = False
        self.last_mouse_pos = QPointF()
        self.window_drag_start = QPoint()
        
        # Начальный зум "по размеру экрана" (fit)
        if not pixmap.isNull():
            w_ratio = self.width() / pixmap.width()
            h_ratio = self.height() / pixmap.height()
            self.scale_factor = min(w_ratio, h_ratio) * 0.95
        
        # Кнопка закрытия
        self.btn_close = OverlayCloseBtn(self)
        self.btn_close.clicked.connect(self.close)
        
        # Настройка фокуса для ESC
        self.setFocusPolicy(Qt.StrongFocus)

    def resizeEvent(self, e):
        # Кнопка всегда справа-сверху
        self.btn_close.move(self.width() - 50, 20)
        super().resizeEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Затемнение фона
        painter.fillRect(self.rect(), QColor(0, 0, 0, 240))
        
        if self.pixmap.isNull():
            return
            
        # Рисуем картинку с учетом зума и смещения
        w = self.pixmap.width() * self.scale_factor
        h = self.pixmap.height() * self.scale_factor
        
        # Центр экрана + смещение пользователя
        center_x = self.width() / 2 + self.offset.x()
        center_y = self.height() / 2 + self.offset.y()
        
        # Итоговый прямоугольник отрисовки
        target_rect = QRectF(
            center_x - w/2, 
            center_y - h/2, 
            w, h
        )
        
        painter.drawPixmap(target_rect, self.pixmap, QRectF(self.pixmap.rect()))

    def get_image_rect(self):
        # Вспомогательный метод для определения границ картинки
        if self.pixmap.isNull(): return QRectF()
        w = self.pixmap.width() * self.scale_factor
        h = self.pixmap.height() * self.scale_factor
        cx = self.width() / 2 + self.offset.x()
        cy = self.height() / 2 + self.offset.y()
        return QRectF(cx - w/2, cy - h/2, w, h)

    def wheelEvent(self, event):
        # Зум колесиком
        delta = event.angleDelta().y()
        zoom_speed = 1.1
        if delta > 0:
            self.scale_factor *= zoom_speed
        else:
            self.scale_factor /= zoom_speed
            
        # Ограничения зума
        self.scale_factor = max(0.05, min(self.scale_factor, 10.0))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            img_rect = self.get_image_rect()
            
            if img_rect.contains(event.position()):
                # Кликнули в картинку -> двигаем картинку
                self.is_dragging_image = True
                self.setCursor(Qt.ClosedHandCursor)
            else:
                # Кликнули в фон -> двигаем всё окно (удобно для не фулл-скрин)
                self.is_dragging_window = True
                self.window_drag_start = event.globalPosition().toPoint() - self.pos()
                
            self.last_mouse_pos = event.position()
            
        elif event.button() == Qt.RightButton:
            # ПКМ = Закрыть
            self.close()

    def mouseMoveEvent(self, event):
        if self.is_dragging_image:
            delta = event.position() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = event.position()
            self.update()
            
        elif self.is_dragging_window:
            new_pos = event.globalPosition().toPoint() - self.window_drag_start
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging_image = False
            self.is_dragging_window = False
            self.setCursor(Qt.ArrowCursor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

class EmojiPicker(QDialog):
    # Код пикера эмодзи без изменений (оставлен для целостности модуля)
    EMOJIS = [
        "😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "🥲", "☺️", "😊", "😇",
        "🙂", "🙃", "😉", "😌", "😍", "🥰", "😘", "😗", "😙", "😚", "😋", "😛",
        "😝", "😜", "🤪", "🤨", "🧐", "🤓", "😎", "🥸", "🤩", "🥳", "😏", "😒",
        "😞", "😔", "😟", "😕", "🙁", "☹️", "😣", "😖", "😫", "😩", "🥺", "😢",
        "😭", "😤", "😠", "😡", "🤬", "🤯", "😳", "🥵", "🥶", "😱", "😨", "😰",
        "😥", "😓", "🤗", "🤔", "🤭", "🤫", "🤥", "😶", "😐", "😑", "😬", "🙄",
        "😯", "😦", "😧", "😮", "😲", "🥱", "😴", "🤤", "😪", "😵", "🤐", "🥴",
        "🤢", "🤮", "🤧", "😷", "🤒", "🤕", "🤑", "🤠", "😈", "👿", "👹", "👺",
        "🤡", "💩", "👻", "💀", "☠️", "👽", "👾", "🤖", "🎃", "😺", "😸", "😹",
        "😻", "😼", "😽", "🙀", "😿", "😾", "👋", "🤚", "🖐️", "✋", "🖖", "👌",
        "🤌", "🤏", "✌️", "🤞", "🤟", "🤘", "🤙", "👈", "👉", "👇", "☝️",
        "👍", "👎", "✊", "👊", "🤛", "🤜", "👏", "🙌", "👐", "🤲", "🤝", "🙏",
        "✍️", "💅", "🤳", "💪", "🦾", "🦵", "🦿", "🦶", "👂", "🦻", "👃", "🧠",
        "🦷", "🦴", "👀", "👁️", "👅", "👄", "💋", "🩸", "❤️", "🧡", "💛", "💚",
        "💙", "💜", "🖤", "🤍", "🤎", "💔", "❣️", "💕", "💞", "💓", "💗", "💖",
        "💘", "💝", "💟", "☮️", "✝️", "☪️", "🕉", "☸️", "✡️", "🔯", "🕎", "☯️",
        "☦️", "🛐", "⛎", "♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑",
        "♒", "♓", "🆔", "⚛️", "🉑", "☢️", "☣️", "📴", "📳", "🈶", "🈚", "🈸",
        "🈺", "🈷️", "✴️", "🆚", "💮", "🉐", "㊙️", "㊗️", "🈴", "🈵", "🈹", "🈲"
    ]
    
    emoji_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Emoji")
        self.setFixedSize(360, 350)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border: 1px solid #d1d5db; border-radius: 8px; }")
        inner_layout = QVBoxLayout(container)
        inner_layout.setContentsMargins(5, 5, 5, 5)
        emoji_grid_widget = QWidget()
        emoji_grid_widget.setStyleSheet("background: transparent; border: none; border-radius: 0px;")
        emoji_grid = QGridLayout(emoji_grid_widget)
        emoji_grid.setSpacing(2)
        emoji_grid.setContentsMargins(5, 5, 5, 5)
        row, col = 0, 0
        MAX_COLS = 8
        for emoji in self.EMOJIS:
            btn = QPushButton(emoji)
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(emoji)
            btn.setStyleSheet("""
                QPushButton { background: transparent; color: #000000; border: none; border-radius: 4px; padding: 0px; margin: 0px; font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif; font-size: 22px; }
                QPushButton:hover { background: #e0e7ff; }
            """)
            btn.clicked.connect(lambda checked, e=emoji: self.on_emoji_clicked(e))
            emoji_grid.addWidget(btn, row, col)
            col += 1
            if col >= MAX_COLS:
                col = 0
                row += 1
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(emoji_grid_widget)
        scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 8px; background: transparent; margin: 0px; }
            QScrollBar::handle:vertical { background: #c7c7c7; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #a0a0a0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        inner_layout.addWidget(scroll_area)
        main_layout.addWidget(container)
        self.setLayout(main_layout)

    def on_emoji_clicked(self, emoji):
        self.emoji_selected.emit(emoji)
        self.close()

    def hideEvent(self, event):
        if self.parent():
            if hasattr(self.parent(), '_last_emoji_close_time'):
                self.parent()._last_emoji_close_time = time.time()
        super().hideEvent(event)