import hashlib
from PySide6.QtWidgets import QWidget, QDialog, QPushButton
from PySide6.QtCore import Qt, QBuffer, Signal, QPoint, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QMovie, QColor, QPen

class CloseBtn(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        bg_col = QColor(255, 60, 60, 255) if self._hover else QColor(255, 255, 255, 30)
        icon_col = Qt.white
        
        r = self.rect().adjusted(2, 2, -2, -2)
        p.setBrush(bg_col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(r)
        
        p.setPen(QPen(icon_col, 2.5, Qt.SolidLine, Qt.RoundCap))
        c = QPointF(r.center())
        offset = 6
        p.drawLine(c.x() - offset, c.y() - offset, c.x() + offset, c.y() + offset)
        p.drawLine(c.x() + offset, c.y() - offset, c.x() - offset, c.y() + offset)

class AvatarViewer(QDialog):
    def __init__(self, raw_data, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(700, 700)
        
        self.movie = None
        self.static_pixmap = None
        self.buffer = None
        
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        
        self._drag_win = False
        self._drag_img = False
        self._last_pos = QPoint()

        self.raw_data = raw_data
        if self.raw_data:
            if self.raw_data[:6].startswith(b'GIF'):
                self.buffer = QBuffer()
                self.buffer.setData(self.raw_data)
                self.buffer.open(QBuffer.ReadOnly)
                self.movie = QMovie(self.buffer, b"GIF")
                self.movie.setCacheMode(QMovie.CacheAll)
                self.movie.frameChanged.connect(lambda: self.update())
                self.movie.start()
            else:
                self.static_pixmap = QPixmap()
                self.static_pixmap.loadFromData(self.raw_data)

        self.btn_close = CloseBtn(self)
        self.btn_close.clicked.connect(self.close)

    def resizeEvent(self, e):
        self.btn_close.move(self.width() - 50, 10)
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        
        p.fillRect(self.rect(), QColor(0, 0, 0, 220))
        
        cur_pix = None
        if self.movie and self.movie.isValid():
            cur_pix = self.movie.currentPixmap()
        elif self.static_pixmap and not self.static_pixmap.isNull():
            cur_pix = self.static_pixmap
            
        if not cur_pix or cur_pix.isNull():
            p.setPen(Qt.white)
            p.drawText(self.rect(), Qt.AlignCenter, "Нет изображения")
            return

        c = self.rect().center()
        w = cur_pix.width() * self.scale_factor
        h = cur_pix.height() * self.scale_factor
        
        r_dest = QRectF(
            c.x() - w/2 + self.offset.x(),
            c.y() - h/2 + self.offset.y(),
            w, h
        )
        p.drawPixmap(r_dest.toRect(), cur_pix)

    def mousePressEvent(self, e):
        if self.childAt(e.pos()) == self.btn_close:
            return
        
        if e.button() == Qt.LeftButton:
            self._last_pos = e.globalPosition().toPoint()
            
            cur_pix = None
            if self.movie:
                cur_pix = self.movie.currentPixmap()
            elif self.static_pixmap:
                cur_pix = self.static_pixmap
            
            is_over_image = False
            if cur_pix and not cur_pix.isNull():
                c = self.rect().center()
                w = cur_pix.width() * self.scale_factor
                h = cur_pix.height() * self.scale_factor
                img_rect = QRectF(c.x() - w/2 + self.offset.x(), c.y() - h/2 + self.offset.y(), w, h)
                if img_rect.contains(e.position()):
                    is_over_image = True
            
            if is_over_image:
                self._drag_img = True
            else:
                self._drag_win = True
            
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            curr = e.globalPosition().toPoint()
            diff = curr - self._last_pos
            self._last_pos = curr
            
            if self._drag_win:
                self.move(self.pos() + diff)
            elif self._drag_img:
                self.offset += diff
                self.update()
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_win = False
        self._drag_img = False

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        f = 1.1 if d > 0 else 0.9
        ns = self.scale_factor * f
        if 0.1 < ns < 10.0:
            self.scale_factor = ns
            self.update()

class CircularAvatar(QWidget):
    clicked = Signal()

    def __init__(self, size=120, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.movie = None
        self.pixmap = None
        self.buf = None 
        self.raw_data = None
        self.char = "?"
        self.bg_col = "#6366f1"

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def set_letter(self, text):
        self.stop_movie()
        self.pixmap = None
        self.raw_data = None
        t = text or "?"
        self.char = t[0].upper()
        h = hashlib.md5(t.encode()).hexdigest()
        self.bg_col = f"#{h[:6]}"
        self.update()

    def set_data(self, data):
        self.raw_data = data
        head = data[:6] if data else b''
        if head.startswith(b'GIF'):
            self.load_gif(data)
        elif data:
            self.load_static(data)
        else:
            self.stop_movie()
            self.update()

    def load_gif(self, data):
        self.stop_movie()
        self.pixmap = None
        self.buf = QBuffer()
        self.buf.setData(data)
        self.buf.open(QBuffer.ReadOnly)
        self.movie = QMovie(self.buf, b"GIF")
        self.movie.setCacheMode(QMovie.CacheAll)
        self.movie.frameChanged.connect(lambda: self.update())
        self.movie.start()

    def load_static(self, data):
        self.stop_movie()
        p = QPixmap()
        p.loadFromData(data)
        self.pixmap = p
        self.update()

    def stop_movie(self):
        if self.movie:
            self.movie.stop()
            self.movie = None
        if self.buf:
            self.buf.close()
            self.buf = None

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addEllipse(0, 0, self.width(), self.height())
        p.setClipPath(path)
        
        if self.movie and self.movie.isValid():
            cur = self.movie.currentPixmap()
            if not cur.isNull():
                self.draw_img(p, cur)
        elif self.pixmap and not self.pixmap.isNull():
            self.draw_img(p, self.pixmap)
        else:
            p.fillRect(self.rect(), QColor(self.bg_col))
            p.setPen(Qt.white)
            f = p.font()
            f.setPixelSize(int(self.height() * 0.5))
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, self.char)

    def draw_img(self, painter, pix):
        w, h = self.width(), self.height()
        scaled = pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)