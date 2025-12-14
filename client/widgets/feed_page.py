from datetime import time
import os
import json
import requests
import feedparser
import webbrowser
import math
from bs4 import BeautifulSoup

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QLineEdit,
    QGridLayout, QDialog, QListWidget, QListWidgetItem,
    QAbstractItemView, QComboBox, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QApplication, QToolTip
)
from PySide6.QtCore import (
    Qt, Signal, QThreadPool, QRunnable, QObject,
    QTimer, QSize, QPropertyAnimation, QPoint, QEasingCurve,
    QRectF, QPointF
)
from PySide6.QtGui import (
    QPixmap, QPainter, QPainterPath, QColor, QCursor,
    QPen, QPalette
)

FILE_RSS = "rss_sources.json"
FILE_BOOKMARKS = "bookmarks.json"
PRIMARY_COLOR = "#6366f1"

class BookmarksManager:
    @staticmethod
    def load():
        if not os.path.exists(FILE_BOOKMARKS):
            return []
        try:
            with open(FILE_BOOKMARKS, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except:
            return []

    @staticmethod
    def save(data):
        current = BookmarksManager.load()
        if not any(x.get('link') == data.get('link') for x in current):
            clean = {k: v for k, v in data.items() if k not in ['pixmap_cache']}
            current.append(clean)
            try:
                with open(FILE_BOOKMARKS, "w", encoding="utf-8") as f:
                    json.dump(current, f, ensure_ascii=False, indent=4)
            except:
                pass

    @staticmethod
    def remove(link):
        current = [x for x in BookmarksManager.load() if x.get('link') != link]
        try:
            with open(FILE_BOOKMARKS, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=4)
        except:
            pass

    @staticmethod
    def is_in(link):
        return any(x.get('link') == link for x in BookmarksManager.load())

class DraggableDialogMixin:
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_active = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        if hasattr(super(), "mousePressEvent"):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_active') and self._drag_active and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        if hasattr(super(), "mouseMoveEvent"):
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self._drag_active = False
        if hasattr(super(), "mouseReleaseEvent"):
            super().mouseReleaseEvent(event)

class RichActionButton(QPushButton):
    def __init__(self, mode="close", size=36, parent=None,
                 base_color=QColor(100, 100, 100, 50),
                 hover_color=QColor("#ef4444"),
                 icon_color=Qt.white):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        self.mode = mode
        self.base_color = base_color
        self.hover_color = hover_color
        self.icon_color = icon_color
        self.is_active = False

    def set_active(self, active: bool):
        self.is_active = active
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        if self.is_active and self.mode == "star":
            bg = QColor("#FFD700")
            icon_c = QColor("#000000")
        elif self._hover:
            bg = self.hover_color
            icon_c = Qt.white
        else:
            bg = self.base_color
            icon_c = self.icon_color

        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawEllipse(rect)

        center = rect.center()

        if self.mode == "close":
            p.setPen(QPen(icon_c, 2.5, Qt.SolidLine, Qt.RoundCap))
            offset = rect.width() * 0.18
            cx, cy = center.x(), center.y()
            p.drawLine(QPointF(cx - offset, cy - offset), QPointF(cx + offset, cy + offset))
            p.drawLine(QPointF(cx + offset, cy - offset), QPointF(cx - offset, cy + offset))

        elif self.mode == "star":
            radius = rect.width() * 0.35
            points = []
            cx, cy = center.x(), center.y()
            for i in range(5):
                angle = math.radians(270 + i * 72)
                points.append(QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
                angle_in = math.radians(270 + i * 72 + 36)
                r_in = radius * 0.45
                points.append(QPointF(cx + r_in * math.cos(angle_in), cy + r_in * math.sin(angle_in)))

            path = QPainterPath()
            if points:
                path.moveTo(points[0])
                for pt in points[1:]:
                    path.lineTo(pt)
                path.closeSubpath()

            p.setPen(Qt.NoPen)
            p.setBrush(icon_c)
            p.drawPath(path)

class Toast(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(350, 50)
        self.setStyleSheet("""
        QFrame { background-color: #334155; border-radius: 25px; border: 1px solid #475569; }
        QLabel { color: white; font-weight: bold; font-size: 14px; border: none; }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setYOffset(5)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        self.lbl = QLabel("Notification")
        self.lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_toast)

        self.opacity_eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_eff)
        self.hide()

    def show_msg(self, text, duration=2500):
        self.lbl.setText(text)
        if self.parentWidget():
            pw, ph = self.parentWidget().width(), self.parentWidget().height()
            self.move((pw - self.width()) // 2, ph - 80)
            self.raise_()
        self.show()

        self.anim = QPropertyAnimation(self.opacity_eff, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()
        self.timer.start(duration)

    def hide_toast(self):
        self.anim = QPropertyAnimation(self.opacity_eff, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.hide)
        self.anim.start()

class CopyUrlWidget(QWidget):
    toast_requested = Signal(str)

    def __init__(self, url, is_dark=True, parent=None):
        super().__init__(parent)
        self.url = url
        self.is_dark = is_dark
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        self.hover_copy = False
        self.update_colors(is_dark)
        self.setToolTip("Нажмите, чтобы скопировать URL")

    def update_colors(self, is_dark):
        self.is_dark = is_dark
        if is_dark:
            self.tag_bg = PRIMARY_COLOR
            self.text_color = "#ccccff"
            self.icon_base_color = "#dddddd"
        else:
            self.tag_bg = PRIMARY_COLOR
            self.text_color = "#333333"
            self.icon_base_color = "#555555"
        self.update()

    def mouseMoveEvent(self, e):
        rect_copy = QRectF(self.width() - 32, 0, 32, 32)
        if rect_copy.contains(e.position()):
            if not self.hover_copy:
                self.hover_copy = True
                self.update()
        else:
            if self.hover_copy:
                self.hover_copy = False
                self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hover_copy = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.url)
        p = self.parentWidget()
        toast_found = False
        while p:
            if hasattr(p, 'toast') and p.toast is not None:
                try:
                    p.toast.show_msg("Ссылка скопирована")
                    toast_found = True
                    break
                except:
                    pass
            p = p.parentWidget()
        if not toast_found:
            QToolTip.showText(QCursor.pos(), "Ссылка скопирована", self)
        super().mousePressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tag_w = 42
        tag_h = 22
        tag_y = (self.height() - tag_h) / 2
        path_tag = QPainterPath()
        path_tag.addRoundedRect(0, tag_y, tag_w, tag_h, 6, 6)
        p.setBrush(QColor(self.tag_bg))
        p.setPen(Qt.NoPen)
        p.drawPath(path_tag)
        p.setPen(Qt.white)
        f_tag = p.font()
        f_tag.setBold(True)
        f_tag.setPixelSize(10)
        p.setFont(f_tag)
        p.drawText(QRectF(0, tag_y, tag_w, tag_h), Qt.AlignCenter, "URL")
        p.setPen(QColor(self.text_color))
        f_text = p.font()
        f_text.setBold(False)
        f_text.setPixelSize(12)
        p.setFont(f_text)
        padding_left = tag_w + 10
        copy_icon_w = 34
        avail_w = self.width() - padding_left - copy_icon_w
        text_rect = QRectF(padding_left, 0, avail_w, self.height())
        elided = p.fontMetrics().elidedText(self.url, Qt.ElideMiddle, int(avail_w))
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)
        cx = self.width() - 16
        cy = self.height() / 2
        icon_col = QColor(self.tag_bg) if self.hover_copy else QColor(self.icon_base_color)
        p.setPen(QPen(icon_col, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline([QPointF(cx - 3, cy - 5), QPointF(cx + 3, cy - 5), QPointF(cx + 3, cy + 3)])
        p.drawRoundedRect(QRectF(cx - 7, cy - 3, 9, 11), 2, 2)

class ImageViewer(QDialog, DraggableDialogMixin):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.orig_pixmap = pixmap
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        self._image_drag = False
        self._last_img_pos = QPoint()
        self.close_btn = RichActionButton(mode="close", size=45, parent=self, icon_color=Qt.white)
        self.close_btn.clicked.connect(self.close)
        self.resize(1000, 700)
        QTimer.singleShot(0, self.setup_ui_pos)

    def setup_ui_pos(self):
        self.showMaximized()
        self.close_btn.raise_()
        self.close_btn.move(self.width() - 80, 50)

    def resizeEvent(self, event):
        if hasattr(self, 'close_btn'):
            self.close_btn.move(self.width() - 80, 50)
        super().resizeEvent(event)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(0, 0, 0, 240))
        if not self.orig_pixmap or self.orig_pixmap.isNull():
            p.setPen(Qt.white)
            p.drawText(self.rect(), Qt.AlignCenter, "Изображение не загружено")
            return
        c = self.rect().center()
        w = self.orig_pixmap.width() * self.scale_factor
        h = self.orig_pixmap.height() * self.scale_factor
        target_rect = QRectF(c.x() - w / 2 + self.offset.x(), c.y() - h / 2 + self.offset.y(), w, h)
        p.drawPixmap(target_rect.toRect(), self.orig_pixmap)
        if self.scale_factor == 1.0:
            p.setPen(QColor(150, 150, 150))
            p.setFont(self.font())
            p.drawText(QRectF(0, self.height() - 40, self.width(), 30), Qt.AlignCenter,
                       "Колесико для Zoom • Drag для перемещения")

    def wheelEvent(self, e):
        factor = 1.1 if e.angleDelta().y() > 0 else 0.9
        if 0.1 < self.scale_factor * factor < 8.0:
            self.scale_factor *= factor
            self.update()

    def mousePressEvent(self, e):
        if self.childAt(e.pos()) == self.close_btn:
            super().mousePressEvent(e)
            return
        if e.button() == Qt.LeftButton:
            self._image_drag = True
            self._last_img_pos = e.pos()

    def mouseMoveEvent(self, e):
        if self._image_drag:
            self.offset += e.pos() - self._last_img_pos
            self._last_img_pos = e.pos()
            self.update()

    def mouseReleaseEvent(self, e):
        self._image_drag = False

class ImgSig(QObject):
    done = Signal(object, object)

class Loader(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.s = ImgSig()

    def run(self):
        try:
            if not self.url:
                self.s.done.emit(None, QPixmap())
                return
            r = requests.get(self.url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                pix = QPixmap()
                pix.loadFromData(r.content)
                self.s.done.emit(self.url, pix)
            else:
                self.s.done.emit(self.url, QPixmap())
        except:
            self.s.done.emit(self.url, QPixmap())

class FeedCard(QFrame):
    def __init__(self, data, is_dark_mode=True, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark = is_dark_mode
        self.setFixedSize(300, 395)
        self.setCursor(Qt.PointingHandCursor)
        self.original_pixmap = QPixmap()
        self.setup_ui()
        self.update_style(is_dark_mode)

    def setup_ui(self):
        l = QVBoxLayout(self)
        l.setContentsMargins(10, 10, 10, 10)
        l.setSpacing(6)
        self.pic = QLabel()
        self.pic.setFixedSize(278, 160)
        self.pic.setAlignment(Qt.AlignCenter)
        self.pic.setStyleSheet("background-color: rgba(127,127,127,0.1); border-radius: 10px;")
        l.addWidget(self.pic)
        row1 = QHBoxLayout()
        self.src = QLabel(self.data['source'])
        self.src.setStyleSheet("font-weight: 800; font-size: 11px; text-transform: uppercase;")
        row1.addWidget(self.src)
        row1.addStretch()
        l.addLayout(row1)
        tt = self.data['title']
        if len(tt) > 60: tt = tt[:57] + "..."
        self.tit = QLabel(tt)
        self.tit.setWordWrap(True)
        self.tit.setAlignment(Qt.AlignTop)
        self.tit.setFixedHeight(55)
        l.addWidget(self.tit)
        st = self.data.get('summary_clean', '')
        if len(st) > 80: st = st[:77] + "..."
        self.summ = QLabel(st)
        self.summ.setWordWrap(True)
        self.summ.setAlignment(Qt.AlignTop)
        l.addWidget(self.summ)
        l.addStretch()
        self.url_widget = CopyUrlWidget(self.data['link'], self.is_dark)
        l.addWidget(self.url_widget)
        img_url = self.data.get('image')
        if img_url and isinstance(img_url, str):
            self.pic.setText("Загрузка...")
            ld = Loader(img_url)
            ld.s.done.connect(self.set_pic)
            QThreadPool.globalInstance().start(ld)
        else:
            self.pic.setText("📷")
            self.pic.setStyleSheet(self.pic.styleSheet() + "font-size: 32px; color: #888;")

    def update_style(self, is_dark):
        self.is_dark = is_dark
        self.url_widget.update_colors(is_dark)
        if is_dark:
            bg_col, border = "#2d2d35", "1px solid #444"
            hover_border = f"1px solid {PRIMARY_COLOR}"
            text_t, text_s, src_col = "white", "#aaa", PRIMARY_COLOR
        else:
            bg_col, border = "#ffffff", "1px solid #d1d5db"
            hover_border = f"2px solid {PRIMARY_COLOR}"
            text_t, text_s, src_col = "#1a1a1a", "#555", PRIMARY_COLOR
        self.setStyleSheet(f"""
            FeedCard {{ background-color: {bg_col}; border-radius: 16px; border: {border}; }}
            FeedCard:hover {{ border: {hover_border}; }}
        """)
        self.tit.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {text_t}; border: none; background: transparent;")
        self.summ.setStyleSheet(f"font-size: 12px; color: {text_s}; border: none; background: transparent;")
        self.src.setStyleSheet(f"color: {src_col}; border: none; background: transparent;")

    def set_pic(self, url, px):
        if not px or px.isNull(): return
        self.original_pixmap = px
        final = QPixmap(self.pic.size())
        final.fill(Qt.transparent)
        p = QPainter(final)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(0, 0, final.width(), final.height(), 10, 10)
        p.setClipPath(path)
        scaled = px.scaled(self.pic.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x, y = (self.pic.width() - scaled.width()) // 2, (self.pic.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        p.end()
        self.pic.setPixmap(final)
        self.pic.setText("")
        self.data['pixmap_cache'] = px

    def mousePressEvent(self, e):
        child = self.childAt(e.pos())
        if isinstance(child, CopyUrlWidget) or (child and isinstance(child.parent(), CopyUrlWidget)):
            super().mousePressEvent(e)
            return
        DetailDialog(self.data, self.is_dark, self.window()).exec()

class DetailDialog(QDialog):
    def __init__(self, data, is_dark, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark = is_dark
        self.toast = Toast(self)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._header_drag_active = False
        self._header_drag_start = QPoint()
        self._window_drag_start_offset = QPoint()
        self.resize(750, 850)
        self.setup_ui()

    def setup_ui(self):
        bg_col = "#1e293b" if self.is_dark else "#ffffff"
        text_p = "white" if self.is_dark else "#1a1a1a"
        text_s = "#cbd5e1" if self.is_dark else "#333333"
        border = "1px solid #475569" if self.is_dark else "1px solid #cbd5e1"
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.card = QFrame(self)
        self.card.setStyleSheet(f"""
            QFrame {{ 
                background-color: {bg_col}; 
                border-radius: 20px; 
                border: {border}; 
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setYOffset(10)
        self.card.setGraphicsEffect(shadow)
        self.main_layout.addWidget(self.card)
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.btn_close = RichActionButton(
            mode="close", 
            size=36, 
            parent=self.card,
            base_color=QColor(0, 0, 0, 100),
            hover_color=QColor("#ef4444"),
            icon_color=Qt.white
        )
        self.btn_close.clicked.connect(self.close)
        self.header_area = QWidget()
        self.header_area.setStyleSheet("background: transparent; border: none; border-top-left-radius: 20px; border-top-right-radius: 20px;")
        self.header_area.mousePressEvent = self.header_press
        self.header_area.mouseMoveEvent = self.header_move
        self.header_area.mouseReleaseEvent = self.header_release
        self.header_area.setCursor(Qt.PointingHandCursor)
        hl = QVBoxLayout(self.header_area)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setStyleSheet("border: none; background: transparent;")
        hl.addWidget(self.img_lbl)
        cl.addWidget(self.header_area)
        w_body = QWidget()
        w_body.setStyleSheet("background: transparent; border: none;") 
        body_lay = QVBoxLayout(w_body)
        body_lay.setContentsMargins(30, 25, 30, 30)
        body_lay.setSpacing(15)
        w_body.mousePressEvent = self.body_press
        w_body.mouseMoveEvent = self.body_move
        meta_row = QHBoxLayout()
        meta = QLabel(f"{self.data.get('source', 'Unknown')} • RSS")
        meta.setStyleSheet(f"color: {PRIMARY_COLOR}; font-weight: 800; border: none; font-size: 13px;")
        meta_row.addWidget(meta)
        meta_row.addStretch()
        self.star_btn = RichActionButton(
            mode="star", size=40,
            base_color=QColor(150, 150, 150, 40),
            hover_color=QColor(PRIMARY_COLOR),
            icon_color=QColor("#555") if not self.is_dark else QColor("#aaa")
        )
        self.star_btn.set_active(BookmarksManager.is_in(self.data['link']))
        self.star_btn.clicked.connect(self.toggle_bookmark)
        meta_row.addWidget(self.star_btn)
        body_lay.addLayout(meta_row)
        tit = QLabel(self.data.get('title', ''))
        tit.setWordWrap(True)
        tit.setAttribute(Qt.WA_TransparentForMouseEvents) 
        tit.setStyleSheet(f"color: {text_p}; font-size: 24px; font-weight: bold; border: none; background: transparent;")
        body_lay.addWidget(tit)
        scroll_txt = QScrollArea()
        scroll_txt.setWidgetResizable(True)
        scroll_txt.setStyleSheet("background: transparent; border: none;")
        content = QLabel(self.data.get('summary', ''))
        content.setWordWrap(True)
        content.setStyleSheet(f"font-size: 16px; line-height: 1.6; color: {text_s}; border: none; background: transparent;")
        content.setOpenExternalLinks(True)
        content.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        scroll_txt.setWidget(content)
        body_lay.addWidget(scroll_txt)
        actions = QHBoxLayout()
        url_w = CopyUrlWidget(self.data['link'], self.is_dark)
        url_w.setFixedWidth(250)
        actions.addWidget(url_w)
        btn_browser = QPushButton("Открыть в браузере")
        btn_browser.setCursor(Qt.PointingHandCursor)
        btn_browser.setStyleSheet(f"QPushButton {{ background: rgba(99,102,241,0.1); color: #6366f1; border: 1px solid #6366f1; border-radius: 10px; padding: 8px 15px; font-weight: bold; }} QPushButton:hover {{ background: #6366f1; color: white; }}")
        btn_browser.clicked.connect(lambda: webbrowser.open(self.data['link']))
        actions.addStretch()
        actions.addWidget(btn_browser)
        body_lay.addLayout(actions)
        cl.addWidget(w_body, 1)
        full_pix = self.data.get('pixmap_cache')
        if full_pix and not full_pix.isNull():
            self.set_header_image(full_pix)
        else:
            if self.data.get('image'):
                self.img_lbl.setText("Загрузка...")
                self.img_lbl.setFixedHeight(120)
                l = Loader(self.data.get('image'))
                l.s.done.connect(lambda u, p: self.set_header_image(p))
                QThreadPool.globalInstance().start(l)
            else:
                self.img_lbl.hide()

    def header_press(self, e):
        if e.button() == Qt.LeftButton:
            self._header_drag_start = e.globalPosition().toPoint()
            self._window_drag_start_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._header_drag_active = False

    def header_move(self, e):
        if e.buttons() & Qt.LeftButton:
            delta = (e.globalPosition().toPoint() - self._header_drag_start).manhattanLength()
            if delta > 5:
                self._header_drag_active = True
                self.move(e.globalPosition().toPoint() - self._window_drag_start_offset)

    def header_release(self, e):
        if e.button() == Qt.LeftButton:
            if not self._header_drag_active:
                self.open_preview(None)
            self._header_drag_active = False

    def body_press(self, e):
        if e.button() == Qt.LeftButton:
            self._body_drag = True
            self._window_drag_start_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def body_move(self, e):
        if getattr(self, '_body_drag', False) and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._window_drag_start_offset)
            e.accept()

    def resizeEvent(self, event):
        if hasattr(self, 'btn_close') and hasattr(self, 'card'):
            m = 15
            self.btn_close.move(self.card.width() - self.btn_close.width() - m, m)
            self.btn_close.raise_()
        super().resizeEvent(event)

    def set_header_image(self, px):
        if not px or px.isNull(): return
        self.data['pixmap_cache'] = px
        MAX_HEIGHT = 350
        target_w = 720
        if self.card.width() > 100: 
            target_w = self.card.width()
        scaled = px.scaledToWidth(target_w, Qt.SmoothTransformation)
        if scaled.height() > MAX_HEIGHT:
            final_h = MAX_HEIGHT
            offset_y = (scaled.height() - MAX_HEIGHT) // 2 
        else:
            final_h = scaled.height()
            offset_y = 0
        radius = 20
        border_fix = 1
        final = QPixmap(target_w, final_h)
        final.fill(Qt.transparent)
        p = QPainter(final)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.moveTo(0, final_h)
        path.lineTo(0, radius)
        path.arcTo(border_fix, border_fix, radius*2, radius*2, 180, -90)
        path.lineTo(target_w - radius, border_fix)
        path.arcTo(target_w - radius*2 - border_fix, border_fix, radius*2, radius*2, 90, -90)
        path.lineTo(target_w, final_h)
        path.lineTo(0, final_h)
        p.setClipPath(path)
        p.drawPixmap(0, -offset_y, scaled) 
        p.end()
        self.img_lbl.setPixmap(final)
        self.img_lbl.setFixedHeight(final_h) 
        if hasattr(self, 'btn_close'): 
            self.btn_close.raise_()

    def open_preview(self, e):
        fp = self.data.get('pixmap_cache')
        if fp and not fp.isNull():
            ImageViewer(fp, self.window()).exec()

    def toggle_bookmark(self):
        if BookmarksManager.is_in(self.data['link']):
            BookmarksManager.remove(self.data['link'])
            self.star_btn.set_active(False)
            self.toast.show_msg("Удалено из избранного")
        else:
            BookmarksManager.save(self.data)
            self.star_btn.set_active(True)
            self.toast.show_msg("Добавлено в избранное")

class GripWidget(QWidget):
    def __init__(self, parent=None, is_dark=True):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setCursor(Qt.SizeAllCursor)
        self.is_dark = is_dark
        self._hover = False
        self.setToolTip("Потяните, чтобы изменить порядок")

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg_col = QColor(255, 255, 255, 15) if self.is_dark else QColor(0, 0, 0, 10)
        if self._hover:
            bg_col = QColor(PRIMARY_COLOR)
            bg_col.setAlpha(80)
        path = QPainterPath()
        path.addRoundedRect(2, 2, 28, 28, 8, 8)
        p.setPen(Qt.NoPen)
        p.setBrush(bg_col)
        p.drawPath(path)
        line_col = QColor(200, 200, 200) if self.is_dark else QColor(80, 80, 80)
        if self._hover:
            line_col = Qt.white
        p.setPen(QPen(line_col, 2, Qt.SolidLine, Qt.RoundCap))
        cx = self.width() / 2
        cy = self.height() / 2
        offset = 5
        p.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))
        p.drawLine(QPointF(cx - 6, cy - offset), QPointF(cx + 6, cy - offset))
        p.drawLine(QPointF(cx - 6, cy + offset), QPointF(cx + 6, cy + offset))

class DraggableListWidget(QListWidget):
    itemDropped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.itemDropped.emit()

class FeedItemRow(QWidget):
    def __init__(self, name, url, on_delete_callback, is_dark=True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(12)
        self.grip = GripWidget(self, is_dark)
        layout.addWidget(self.grip)
        text_cont = QVBoxLayout()
        text_cont.setSpacing(3)
        text_cont.setContentsMargins(0, 4, 0, 4)
        t_col = "white" if is_dark else "#1a1a1a"
        u_col = "#94a3b8" if is_dark else "#64748b"
        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {t_col}; border: none; background: transparent;")
        self.lbl_url = QLabel(url)
        self.lbl_url.setStyleSheet(f"font-size: 11px; color: {u_col}; border: none; background: transparent;")
        metrics = self.lbl_url.fontMetrics()
        elided_url = metrics.elidedText(url, Qt.ElideRight, 200)
        self.lbl_url.setText(elided_url)
        text_cont.addWidget(self.lbl_name)
        text_cont.addWidget(self.lbl_url)
        layout.addLayout(text_cont)
        layout.addStretch()
        self.btn_del = RichActionButton(
            mode="close", size=32, 
            base_color=QColor(255, 80, 80, 20) if is_dark else QColor(255, 0, 0, 20), 
            hover_color=QColor(255, 60, 60), 
            icon_color=QColor("#ffcccc") if is_dark else QColor("#cc0000")
        )
        self.btn_del.setToolTip("Удалить")
        self.btn_del.clicked.connect(on_delete_callback)
        layout.addWidget(self.btn_del)

class ManageDialog(DraggableDialogMixin, QDialog):
    def __init__(self, feeds, is_dark, parent=None):
        super().__init__(parent)
        self.feeds = list(feeds)
        self.is_dark = is_dark
        self.modified = False
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(540, 740)
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(20, 20, 20, 20)
        self.main_frame = QFrame(self)
        dialog_layout.addWidget(self.main_frame)
        self.setup_style()
        self.setup_ui()

    def setup_style(self):
        bg = "#1e293b" if self.is_dark else "#ffffff"
        border = "1px solid #475569" if self.is_dark else "1px solid #cbd5e1"
        txt_h = "white" if self.is_dark else "#1a1a1a"
        inp_bg = "rgba(0,0,0,0.2)" if self.is_dark else "#f1f5f9"
        list_border = "#334155" if self.is_dark else "#e2e8f0"
        item_hover_border = "#475569" if self.is_dark else "#cbd5e1"
        self.main_frame.setStyleSheet(f"""
            QFrame#MainFrame {{
                background-color: {bg};
                border: {border};
                border-radius: 16px;
            }}
            QLabel {{ color: {txt_h}; }}
            QLineEdit {{
                background-color: {inp_bg};
                border: 1px solid #475569;
                border-radius: 8px;
                padding: 10px;
                color: {txt_h};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_COLOR};
            }}
            QListWidget {{
                background-color: transparent;
                border: 2px solid {list_border};
                border-radius: 12px;
                outline: none;
                padding: 5px;
            }}
            QListWidget::item {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                margin-bottom: 4px;
            }}
            QListWidget::item:hover {{
                border: 1px solid {item_hover_border};
            }}
            QListWidget::item:selected {{
                background-color: transparent;
                border: 2px solid {PRIMARY_COLOR};
            }}
            QListWidget::item:selected:hover {{
                border: 2px solid {PRIMARY_COLOR}; 
            }}
        """)
        self.main_frame.setObjectName("MainFrame")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30); shadow.setColor(QColor(0,0,0,80)); shadow.setYOffset(10)
        self.main_frame.setGraphicsEffect(shadow)

    def setup_ui(self):
        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(30, 25, 30, 30)
        layout.setSpacing(15)

        top = QHBoxLayout()
        title = QLabel("Источники RSS")
        title.setStyleSheet("font-size: 22px; font-weight: 800; border: none;")
        self.btn_close = RichActionButton(mode="close", size=34, parent=self.main_frame, icon_color=Qt.white if self.is_dark else Qt.black)
        self.btn_close.clicked.connect(self.reject)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.btn_close)
        layout.addLayout(top)

        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Название сайта")
        self.inp_url = QLineEdit()
        self.inp_url.setPlaceholderText("https://...")
        self.btn_add = QPushButton("Добавить ленту")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setFixedHeight(42)
        self.btn_add.setStyleSheet(f"QPushButton {{ background-color: {PRIMARY_COLOR}; color: white; border-radius: 10px; font-weight: bold; border:none; font-size: 14px; }} QPushButton:hover {{ background-color: #4f46e5; }}")
        self.btn_add.clicked.connect(self.add_source)
        
        layout.addWidget(self.inp_name)
        layout.addWidget(self.inp_url)
        layout.addWidget(self.btn_add)
        
        layout.addSpacing(10)
        
        il = QHBoxLayout()
        il.setContentsMargins(0, 0, 0, 0)
        sub_col = "#94a3b8" if self.is_dark else "#64748b"
        l = QLabel("АКТИВНЫЕ ПОДПИСКИ")
        l.setStyleSheet(f"color: {sub_col}; font-weight: bold; font-size: 11px; border:none;")
        il.addWidget(l)
        il.addStretch()
        layout.addLayout(il)

        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Поиск подписки по имени или ссылке...")
        self.inp_search.setFixedHeight(40)
        
        s_bg = "rgba(255, 255, 255, 0.07)" if self.is_dark else "#f1f5f9"
        s_border = "#475569" if self.is_dark else "#cbd5e1"
        s_text = "white" if self.is_dark else "#1e293b"
        
        self.inp_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {s_bg};
                border: 1px solid {s_border};
                border-radius: 20px;
                padding: 0 15px;
                color: {s_text};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_COLOR};
                background-color: {s_bg};
            }}
        """)
        self.inp_search.textChanged.connect(self.filter_subscriptions)
        layout.addWidget(self.inp_search)

        self.list_w = DraggableListWidget()
        self.list_w.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_w.itemDropped.connect(self.handle_reorder)
        layout.addWidget(self.list_w)
        self.render_list()

        hb = QHBoxLayout()
        hb.setSpacing(15)
        bc = QPushButton("Отмена")
        bc.setFixedHeight(48)
        bc.setCursor(Qt.PointingHandCursor)
        bc.clicked.connect(self.reject)
        cancel_brd = "#475569" if self.is_dark else "#cbd5e1"
        cancel_txt = "#cbd5e1" if self.is_dark else "#64748b"
        bc.setStyleSheet(f"QPushButton {{ background: transparent; border: 1px solid {cancel_brd}; color: {cancel_txt}; border-radius: 12px; font-size: 14px; }} QPushButton:hover {{ border-color: {PRIMARY_COLOR}; color: {PRIMARY_COLOR}; }}")
        
        bs = QPushButton("Сохранить")
        bs.setFixedHeight(48)
        bs.setCursor(Qt.PointingHandCursor)
        bs.clicked.connect(self.save_all)
        bs.setStyleSheet(f"QPushButton {{ background: {PRIMARY_COLOR}; color: white; font-weight: bold; border-radius: 12px; font-size: 15px; border: none; }} QPushButton:hover {{ background: #4f46e5; }}")
        
        hb.addWidget(bc)
        hb.addWidget(bs, 1)
        layout.addLayout(hb)

    def filter_subscriptions(self, text):
            search_text = text.lower().strip()
            for i in range(self.list_w.count()):
                item = self.list_w.item(i)
                data = item.data(Qt.UserRole) 
                if not data:
                    continue
                    
                name = data.get('name', '').lower()
                url = data.get('url', '').lower()
                
                should_show = (search_text in name) or (search_text in url)
                item.setHidden(not should_show)

    def render_list(self):
        self.list_w.clear()
        for idx, f in enumerate(self.feeds):
            item = QListWidgetItem(self.list_w)
            item.setSizeHint(QSize(0, 68))
            item.setData(Qt.UserRole, f)
            row = FeedItemRow(f['name'], f['url'], lambda i=idx: self.remove_source(i), is_dark=self.is_dark, parent=self.list_w)
            self.list_w.setItemWidget(item, row)

    def handle_reorder(self):
        nf = []
        for i in range(self.list_w.count()):
            d = self.list_w.item(i).data(Qt.UserRole)
            if d: nf.append(d)
        self.feeds = nf
        self.render_list()

    def add_source(self):
        n, u = self.inp_name.text().strip(), self.inp_url.text().strip()
        if not n or not u: return
        self.feeds.append({"name": n, "url": u})
        self.inp_name.clear(); self.inp_url.clear(); self.render_list(); self.list_w.scrollToBottom()

    def remove_source(self, index):
        if 0 <= index < len(self.feeds): del self.feeds[index]; self.render_list()

    def save_all(self):
        self.modified = True; self.accept()

class FeedWorker(QRunnable):
    def __init__(self, feeds, parent=None):
        super().__init__()
        self.feeds = feeds
        self.sig = ImgSig()  # Создаем в основном потоке
        self._is_running = True  # Флаг для остановки

    def run(self):
        out = []
        seen_links = set()
        
        if not self._is_running:
            return
            
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

        for s in self.feeds:
            if not self._is_running:
                break
                
            try:
                resp = requests.get(s['url'], headers=headers, timeout=10)
                if resp.status_code == 200:
                    d = feedparser.parse(resp.content)
                    
                    for e in d.entries[:10]:
                        if not self._is_running:
                            break
                            
                        link = e.get('link', '')
                        if not link or link in seen_links:
                            continue
                        seen_links.add(link)

                        dt = e.get('published_parsed') or e.get('updated_parsed')
                        if not dt:
                            dt = time.gmtime(0)

                        img = None
                        if 'media_content' in e:
                            try: 
                                img = e.media_content[0]['url']
                            except: 
                                pass
                        elif 'links' in e:
                            for l in e.links:
                                if l.get('type', '').startswith('image/'):
                                    img = l['href']
                                    break
                        
                        summary = e.get('summary', '') or e.get('description', '')
                        if not img:
                            try:
                                so = BeautifulSoup(summary, 'html.parser')
                                tag = so.find('img')
                                if tag and tag.get('src'):
                                    img = tag['src']
                            except:
                                pass
                        
                        try:
                            clean_text = BeautifulSoup(summary, 'html.parser').get_text()[:150].strip()
                        except:
                            clean_text = ""

                        out.append({
                            'source': s['name'], 
                            'title': e.get('title', 'Без названия'), 
                            'link': link,
                            'summary': summary, 
                            'summary_clean': clean_text, 
                            'image': img,
                            'timestamp': dt
                        })

            except Exception as e:
                print(f"[FeedWorker] Ошибка загрузки {s['url']}: {e}")

        out.sort(key=lambda x: x['timestamp'], reverse=True)
        
        if self._is_running:
            self.sig.done.emit(out, None)

    def stop(self):
        self._is_running = False

class FeedPage(QWidget):
    def __init__(self):
        super().__init__()
        self.is_dark_mode = True
        self.feeds = self.load_feeds()
        self.all_posts = []
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 0)
        top = QHBoxLayout()
        self.lbl_head = QLabel("Новости")
        self.lbl_head.setStyleSheet("font-size: 28px; font-weight: 800; border: none;")
        self.filter = QComboBox()
        self.filter.setFixedSize(200, 40)
        self.filter.setCursor(Qt.PointingHandCursor)
        self.filter.currentIndexChanged.connect(self.apply_filter)
        self.btn_man = QPushButton("⚙ Управление")
        self.btn_man.setFixedSize(140, 40)
        self.btn_man.clicked.connect(self.open_manage)
        self.btn_upd = QPushButton("↻ Обновить")
        self.btn_upd.setFixedSize(140, 40)
        self.btn_upd.clicked.connect(self.load_feed)
        top.addWidget(self.lbl_head)
        top.addSpacing(20)
        top.addWidget(self.filter)
        top.addStretch()
        top.addWidget(self.btn_man)
        top.addWidget(self.btn_upd)
        l.addLayout(top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.grid_w = QWidget()
        self.grid = QGridLayout(self.grid_w)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.grid.setSpacing(25)
        self.scroll.setWidget(self.grid_w)
        l.addWidget(self.scroll)
        self.toast = Toast(self)
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.recalc_layout)
        self.update_combos()
        QTimer.singleShot(100, self.load_feed)

    def showEvent(self, e):
        self.is_dark_mode = (self.palette().color(QPalette.Window).lightness() < 128)
        self.apply_theme_styles()
        if self.filter.currentText() == "Избранное":
            self.apply_filter()
        else:
            for i in range(self.grid.count()):
                w = self.grid.itemAt(i).widget()
                if isinstance(w, FeedCard):
                    w.update_style(self.is_dark_mode)
        super().showEvent(e)

    def apply_theme_styles(self):
        dark = self.is_dark_mode
        text_h = "white" if dark else "#1a1a1a"
        btn_bg, btn_fg = ("#33333f", "white") if dark else ("white", "#333")
        btn_border = "1px solid #555" if dark else "1px solid #ccc"
        self.lbl_head.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {text_h}; border: none;")
        self.btn_man.setStyleSheet(
            f"QPushButton {{ background: {btn_bg}; color: {btn_fg}; border: {btn_border}; border-radius: 12px; font-weight: bold; }} QPushButton:hover {{ border: 1px solid {PRIMARY_COLOR}; color: {PRIMARY_COLOR}; }}")
        self.btn_upd.setStyleSheet(self.btn_man.styleSheet())
        c_bg, c_fg = ("#25252e", "white") if dark else ("white", "black")
        self.filter.setStyleSheet(
            f"QComboBox {{ background: {c_bg}; color: {c_fg}; border: {btn_border}; border-radius: 12px; padding-left: 10px; }} QComboBox QAbstractItemView {{ background: {c_bg}; color: {c_fg}; selection-background-color: {PRIMARY_COLOR}; }} QComboBox::drop-down {{ border: none; }}")
        self.scroll.setStyleSheet("background: transparent;")
        self.grid_w.setStyleSheet("background: transparent;")

    def load_feeds(self):
        if os.path.exists(FILE_RSS):
            try:
                with open(FILE_RSS, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return [{"name": "Habr", "url": "https://habr.com/ru/rss/best/daily/"}]

    def update_combos(self):
        c = self.filter.currentText()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("Все источники")
        self.filter.addItem("Избранное")
        for f in self.feeds:
            self.filter.addItem(f['name'])
        idx = self.filter.findText(c)
        if idx >= 0:
            self.filter.setCurrentIndex(idx)
        else:
            self.filter.setCurrentIndex(0)
        self.filter.blockSignals(False)

    def open_manage(self):
        d = ManageDialog(self.feeds, self.is_dark_mode, self.window())
        if d.exec() and d.modified:
            self.feeds = d.feeds
            with open(FILE_RSS, 'w', encoding='utf-8') as f:
                json.dump(self.feeds, f, indent=4)
            self.update_combos()
            self.load_feed()
            self.toast.show_msg("Источники сохранены")

    def load_feed(self):
        if self.filter.currentText() == "Избранное":
            self.apply_filter()
            self.toast.show_msg("Избранное обновлено")
            return
        self.btn_upd.setText("Загрузка...")
        self.btn_upd.setEnabled(False)
        w = FeedWorker(self.feeds)
        w.sig.done.connect(self.on_data)
        QThreadPool.globalInstance().start(w)

    def on_data(self, data, _):
        self.all_posts = data
        self.btn_upd.setText("↻ Обновить")
        self.btn_upd.setEnabled(True)
        self.apply_filter()
        self.toast.show_msg(f"Обновлено: {len(data)} новостей")

    def apply_filter(self):
        target = self.filter.currentText()
        if target == "Избранное":
            self.curr_list = list(reversed(BookmarksManager.load()))
        else:
            self.curr_list = self.all_posts if target == "Все источники" else [p for p in self.all_posts if p['source'] == target]
        self.recalc_layout()

    def resizeEvent(self, e):
        self.resize_timer.start(200)
        if self.toast.isVisible():
            self.toast.move((self.width() - 350) // 2, self.height() - 80)
        super().resizeEvent(e)

    def recalc_layout(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not hasattr(self, 'curr_list') or not self.curr_list:
            return
        cols = max(1, (self.scroll.width() - 40) // 325)
        for i, d in enumerate(self.curr_list):
            self.grid.addWidget(FeedCard(d, self.is_dark_mode), i // cols, i % cols)