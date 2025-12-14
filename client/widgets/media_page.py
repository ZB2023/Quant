import requests
import urllib3
import os
import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QFileDialog, QStackedWidget,
    QGridLayout, QSlider, QDialog, QComboBox, QMessageBox,
    QGraphicsDropShadowEffect, QMenu
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer, QThread, QPoint, QRectF
from PySide6.QtGui import QColor, QPixmap, QPainter, QPainterPath, QPen, QBrush
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

urllib3.disable_warnings()

API_URL = "https://localhost:8001"
ACCENT_COLOR = "#6366f1"

MENU_STYLE = """
QMenu {
    background-color: #1e293b;
    color: #ffffff;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    background: transparent;
    padding: 6px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #6366f1;
    color: white;
}
"""

class APIWorker(QThread):
    finished = Signal(object)
    
    def __init__(self, endpoint, data=None, method="GET"):
        super().__init__()
        self.endpoint = endpoint
        self.data = data
        self.method = method
    
    def run(self):
        try:
            url = f"{API_URL}{self.endpoint}"
            if self.method == "POST":
                r = requests.post(url, json=self.data, verify=False, timeout=30)
            elif self.method == "DELETE":
                r = requests.delete(url, json=self.data, verify=False, timeout=10)
            elif self.method == "PUT":
                r = requests.put(url, json=self.data, verify=False, timeout=10)
            else:
                r = requests.get(url, params=self.data or {}, verify=False, timeout=10)
            
            if r.status_code == 200:
                self.finished.emit(r.json())
            else:
                self.finished.emit(None)
        except Exception:
            self.finished.emit(None)
    
    def stop(self):
        self.quit()
        self.wait()

class SeekSlider(QSlider):
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * e.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(int(val))
            e.accept()
        super().mousePressEvent(e)

class VinylWidget(QWidget):
    def __init__(self, size=60):
        super().__init__()
        self.setFixedSize(size, size)
        self.angle = 0
        self.progress_factor = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.cover_pixmap = None
    
    def rotate(self):
        self.angle = (self.angle + 2) % 360
        self.update()
    
    def set_playing(self, p):
        if p:
            self.timer.start(30)
        else:
            self.timer.stop()
    
    def set_progress(self, c, t):
        self.progress_factor = c / t if t > 0 else 0.0
        self.update()
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        center = rect.center()
        rad = (min(rect.width(), rect.height()) / 2) - 2
        
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#111111"))
        p.drawEllipse(center, rad, rad)
        
        for i in range(1, 4):
            gr_rad = rad * (0.4 + i * 0.15)
            p.setPen(QPen(QColor("#222222"), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(center, gr_rad, gr_rad)
        
        p.save()
        p.translate(center)
        p.rotate(self.angle)
        
        d_rad = rad * 0.35
        
        if self.cover_pixmap:
            path = QPainterPath()
            path.addEllipse(QPoint(0, 0), d_rad, d_rad)
            p.setClipPath(path)
            p.drawPixmap(QRectF(-d_rad, -d_rad, d_rad * 2, d_rad * 2), self.cover_pixmap, self.cover_pixmap.rect())
            p.setClipping(False)
        else:
            p.setBrush(QColor(ACCENT_COLOR))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPoint(0, 0), d_rad, d_rad)
        
        p.setBrush(QColor("#000000"))
        p.drawEllipse(QPoint(0, 0), 3, 3)
        p.restore()
        
        if self.progress_factor > 0:
            p.setPen(QPen(QColor(ACCENT_COLOR), 3))
            start_angle = 90 * 16
            span_angle = -(self.progress_factor * 360) * 16
            p.drawArc(QRectF(center.x() - rad, center.y() - rad, rad * 2, rad * 2), int(start_angle), int(span_angle))

class BaseMediaDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._dragging = False
        self._drag_start = QPoint()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.container = QFrame()
        self.container.setObjectName("AuthCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.container.setGraphicsEffect(shadow)
        
        layout.addWidget(self.container)
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        header = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setObjectName("Header")
        lbl.setStyleSheet("font-size: 18px;")
        
        cls_btn = QPushButton("✕")
        cls_btn.setFixedSize(30, 30)
        cls_btn.setCursor(Qt.PointingHandCursor)
        cls_btn.setStyleSheet("border: none; font-size: 16px; color: #94a3b8;")
        cls_btn.clicked.connect(self.reject)
        
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(cls_btn)
        self.main_layout.addLayout(header)
    
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = e.globalPosition().toPoint() - self.pos()
    
    def mouseMoveEvent(self, e):
        if self._dragging:
            self.move(e.globalPosition().toPoint() - self._drag_start)
    
    def mouseReleaseEvent(self, e):
        self._dragging = False

class GroupDialog(BaseMediaDialog):
    def __init__(self, mode="add", data=None, parent=None):
        t = "Создать альбом" if mode == "add" else "Редактировать альбом"
        super().__init__(t, parent)
        self.resize(400, 450)
        self.cover_path = ""
        self.mode = mode
        
        self.inp_title = QLineEdit()
        self.inp_title.setPlaceholderText("Название альбома")
        self.inp_author = QLineEdit()
        self.inp_author.setPlaceholderText("Исполнитель оригинала")
        self.inp_genre = QLineEdit()
        self.inp_genre.setPlaceholderText("Жанр")
        
        self.btn_cover = QPushButton("📂 Выбрать обложку")
        self.btn_cover.setCursor(Qt.PointingHandCursor)
        self.btn_cover.setStyleSheet("border: 1px dashed #6366f1; border-radius: 8px; padding: 10px; color: #6366f1;")
        self.btn_cover.clicked.connect(self.pick_cover)
        
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self.accept)
        
        if data:
            self.inp_title.setText(data.get('title', ''))
            self.inp_author.setText(data.get('author', ''))
            self.inp_genre.setText(data.get('genre', ''))
            self.cover_path = data.get('cover_path', '')
            if self.cover_path:
                self.btn_cover.setText(f"✓ {os.path.basename(self.cover_path)}")
        
        self.main_layout.addWidget(self.inp_title)
        self.main_layout.addWidget(self.inp_author)
        self.main_layout.addWidget(self.inp_genre)
        self.main_layout.addWidget(self.btn_cover)
        self.main_layout.addStretch()
        self.main_layout.addWidget(self.btn_save)
    
    def pick_cover(self):
        f, _ = QFileDialog.getOpenFileName(self, "Обложка", "", "Images (*.png *.jpg *.jpeg)")
        if f:
            self.cover_path = f
            self.btn_cover.setText(f"✓ {os.path.basename(f)}")
            self.btn_cover.setStyleSheet("border: 1px solid #22c55e; border-radius: 8px; padding: 10px; color: #22c55e;")

class TrackDialog(BaseMediaDialog):
    def __init__(self, mode="add", data=None, group_id=None, existing_tracks=None, parent=None):
        t = "Добавить трек" if mode == "add" else "Редактировать трек"
        super().__init__(t, parent)
        self.resize(400, 550)
        self.group_id = group_id
        self.file_path = ""
        self.existing = existing_tracks or []
        self.originals = [k for k in self.existing if k.get('is_original', True)]
        
        self.inp_title = QLineEdit()
        self.inp_title.setPlaceholderText("Название трека")
        self.inp_perf = QLineEdit()
        self.inp_perf.setPlaceholderText("Исполнитель")
        
        lbl_type = QLabel("Тип трека")
        lbl_type.setObjectName("SubTitle")
        
        self.type_box = QComboBox()
        self.type_box.addItems(["Оригинал", "Кавер/Перепевка"])
        self.type_box.currentIndexChanged.connect(self.on_type_changed)
        
        lbl_parent = QLabel("Связанный оригинал")
        lbl_parent.setObjectName("SubTitle")
        self.combo_parents = QComboBox()
        self.combo_parents.addItem("Выберите оригинал...")
        for org in self.originals:
            self.combo_parents.addItem(f"{org['title']} ({org['performer']})", org['id'])
        self.combo_parents.setEnabled(False)
        
        self.inp_lang = QLineEdit()
        self.inp_lang.setPlaceholderText("Язык исполнения")
        
        self.inp_rate = QLineEdit()
        self.inp_rate.setPlaceholderText("Рейтинг (0-5)")
        self.inp_rate.setText("5")
        
        self.btn_file = QPushButton("🎵 Выбрать аудиофайл")
        self.btn_file.setCursor(Qt.PointingHandCursor)
        self.btn_file.setStyleSheet("border: 1px dashed #6366f1; border-radius: 8px; padding: 10px; color: #6366f1;")
        self.btn_file.clicked.connect(self.pick_file)
        
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self.save)
        
        if data:
            self.inp_title.setText(data.get('title', ''))
            self.inp_perf.setText(data.get('performer', ''))
            self.inp_lang.setText(data.get('language', ''))
            self.inp_rate.setText(str(data.get('rating', 0)))
            self.file_path = data.get('file_path', '')
            if self.file_path:
                self.btn_file.setText(f"✓ {os.path.basename(self.file_path)}")
            is_o = data.get('is_original', True)
            self.type_box.setCurrentIndex(0 if is_o else 1)
            if not is_o:
                pid = data.get('parent_id')
                for i in range(self.combo_parents.count()):
                    if self.combo_parents.itemData(i) == pid:
                        self.combo_parents.setCurrentIndex(i)
                        break
        
        self.main_layout.addWidget(self.inp_title)
        self.main_layout.addWidget(self.inp_perf)
        self.main_layout.addWidget(lbl_type)
        self.main_layout.addWidget(self.type_box)
        self.main_layout.addWidget(lbl_parent)
        self.main_layout.addWidget(self.combo_parents)
        self.main_layout.addWidget(self.inp_lang)
        self.main_layout.addWidget(self.inp_rate)
        self.main_layout.addWidget(self.btn_file)
        self.main_layout.addStretch()
        self.main_layout.addWidget(self.btn_save)
    
    def on_type_changed(self, idx):
        self.combo_parents.setEnabled(idx == 1)
    
    def pick_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Аудио", "", "Audio (*.mp3 *.wav *.flac *.ogg *.m4a)")
        if f:
            self.file_path = f
            self.btn_file.setText(f"✓ {os.path.basename(f)}")
            self.btn_file.setStyleSheet("border: 1px solid #22c55e; border-radius: 8px; padding: 10px; color: #22c55e;")
    
    def save(self):
        if not self.file_path or not self.inp_title.text():
            QMessageBox.warning(self, "Ошибка", "Заполните название и выберите файл")
            return
        
        parent_id = None
        is_orig = (self.type_box.currentIndex() == 0)
        
        if not is_orig:
            idx = self.combo_parents.currentIndex()
            if idx > 0:
                parent_id = self.combo_parents.itemData(idx)
            else:
                QMessageBox.warning(self, "Ошибка", "Выберите оригинал")
                return
        
        try:
            rt = int(self.inp_rate.text())
        except:
            rt = 0
        
        self.accept_data = {
            "group_id": self.group_id,
            "title": self.inp_title.text(),
            "performer": self.inp_perf.text(),
            "is_original": is_orig,
            "parent_id": parent_id,
            "language": self.inp_lang.text(),
            "rating": rt,
            "file_path": self.file_path
        }
        self.accept()

class StarRatingWidget(QWidget):
    def __init__(self, rating=0, parent=None):
        super().__init__(parent)
        self.rating = rating
        self.setFixedSize(50, 20)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        cx, cy = 10, 10
        outer_radius = 8
        inner_radius = 4
        
        angle = math.pi / 2 * 3 
        step = math.pi / 5
        
        path.moveTo(cx + math.cos(angle) * outer_radius, cy + math.sin(angle) * outer_radius)
        for i in range(5):
            angle += step
            path.lineTo(cx + math.cos(angle) * inner_radius, cy + math.sin(angle) * inner_radius)
            angle += step
            path.lineTo(cx + math.cos(angle) * outer_radius, cy + math.sin(angle) * outer_radius)
        path.closeSubpath()
        
        color = QColor("#fbbf24") if self.rating > 0 else QColor("#475569")
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawPath(path)

        p.setPen(QColor("#fbbf24"))
        p.setFont(self.font())
        p.drawText(QRectF(22, 0, 30, 20), Qt.AlignVCenter | Qt.AlignLeft, str(self.rating))

class TrackRowWidget(QFrame):
    play_requested = Signal(str, str, str)
    edit_requested = Signal(dict)
    delete_requested = Signal(dict)
    
    def __init__(self, track_data, is_cover=False):
        super().__init__()
        self.track_data = track_data
        
        if is_cover:
            self.setObjectName("MediaItemCover")
            self.setStyleSheet("QFrame#MediaItemCover { border: none; border-left: 2px solid #6366f1; background-color: rgba(255, 255, 255, 0.03); border-radius: 4px; } QFrame#MediaItemCover:hover { background-color: rgba(99, 102, 241, 0.1); }")
        else:
            self.setObjectName("MediaItem")
            self.setStyleSheet("QFrame#MediaItem { background-color: rgba(255, 255, 255, 0.05); border-radius: 8px; border: 1px solid transparent; } QFrame#MediaItem:hover { border: 1px solid #6366f1; }")
        
        self.setFixedHeight(55 if not is_cover else 45)
        self.setCursor(Qt.PointingHandCursor)
        
        l = QHBoxLayout(self)
        l.setContentsMargins(10, 5, 15, 5)
        l.setSpacing(15)
        
        self.btn_play = QPushButton("▶")
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self.on_play)
        
        if is_cover:
            self.btn_play.setFixedSize(28, 28)
            self.btn_play.setStyleSheet(f"background: #10b981; border-radius: 14px; color: white; border: none; font-size: 10px; font-weight: bold;")
        else:
            self.btn_play.setFixedSize(32, 32)
            self.btn_play.setStyleSheet(f"background: {ACCENT_COLOR}; border-radius: 16px; color: white; border: none; font-size: 14px; font-weight: bold;")
        
        t_col = QVBoxLayout()
        t_col.setSpacing(0)
        t_col.setAlignment(Qt.AlignVCenter)
        
        title = QLabel(track_data['title'])
        title.setObjectName("NormalText")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        perf = QLabel(f"{track_data['performer']} • {track_data['language']}")
        perf.setObjectName("SubTitle")
        
        t_col.addWidget(title)
        t_col.addWidget(perf)
        
        self.rate_widget = StarRatingWidget(track_data.get('rating', 0))
        
        l.addWidget(self.btn_play)
        l.addLayout(t_col)
        l.addStretch()
        l.addWidget(self.rate_widget)
        
        self.arrow = QLabel("")
        self.arrow.setStyleSheet("border: none; font-size: 14px; color: #94a3b8;")
        self.arrow.setVisible(False)
        l.addWidget(self.arrow)
    
    def update_icon(self, current_path, is_playing):
        if self.track_data.get('file_path') == current_path:
            self.btn_play.setText("⏸" if is_playing else "▶")
        else:
            self.btn_play.setText("▶")
    
    def on_play(self):
        self.play_requested.emit(self.track_data['file_path'], self.track_data['title'], self.track_data['performer'])
    
    def set_expanded(self, expanded):
        self.arrow.setText("▼" if expanded else "◀")
    
    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(MENU_STYLE)
        a_edit = m.addAction("Редактировать")
        a_del = m.addAction("Удалить")
        act = m.exec(e.globalPos())
        if act == a_edit:
            self.edit_requested.emit(self.track_data)
        elif act == a_del:
            self.delete_requested.emit(self.track_data)
    
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if not self.arrow.isVisible():
                self.on_play()
        super().mousePressEvent(e)

class TreeTrackWidget(QWidget):
    play_signal_propagate = Signal(str, str, str, object)
    edit_signal = Signal(dict)
    delete_signal = Signal(dict)
    
    def __init__(self, original_data, covers_data):
        super().__init__()
        self.original = original_data
        self.covers = covers_data
        self.rows = []
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 5)
        self.layout.setSpacing(2)
        
        self.header = TrackRowWidget(self.original, is_cover=False)
        self.header.play_requested.connect(self.emit_play)
        self.header.edit_requested.connect(self.edit_signal.emit)
        self.header.delete_requested.connect(self.delete_signal.emit)
        self.rows.append(self.header)
        
        if self.covers:
            self.header.setCursor(Qt.PointingHandCursor)
            self.header.arrow.setVisible(True)
            self.header.set_expanded(False)
            self.header.mousePressEvent = self.on_header_click
        
        self.layout.addWidget(self.header)
        
        self.covers_container = QWidget()
        if self.covers:
            c_layout = QVBoxLayout(self.covers_container)
            c_layout.setContentsMargins(30, 0, 0, 10)
            c_layout.setSpacing(5)
            
            for c in self.covers:
                cw = TrackRowWidget(c, is_cover=True)
                cw.play_requested.connect(self.emit_play)
                cw.edit_requested.connect(self.edit_signal.emit)
                cw.delete_requested.connect(self.delete_signal.emit)
                self.rows.append(cw)
                c_layout.addWidget(cw)
            
            self.layout.addWidget(self.covers_container)
            self.covers_container.hide()
    
    def on_header_click(self, event):
        if event.button() == Qt.LeftButton:
            btn_rect = self.header.btn_play.geometry()
            click_pos = event.position().toPoint()
            
            if btn_rect.contains(click_pos):
                self.header.on_play()
                return
            
            if not self.covers:
                self.header.on_play()
                return
            
            if self.covers_container.isVisible():
                self.covers_container.hide()
                self.header.set_expanded(False)
            else:
                self.covers_container.show()
                self.header.set_expanded(True)
    
    def update_icons(self, path, playing):
        for r in self.rows:
            r.update_icon(path, playing)
    
    def emit_play(self, path, title, perf):
        self.play_signal_propagate.emit(path, title, perf, None)

class PlayerWidget(QFrame):
    def __init__(self, media_page):
        super().__init__()
        self.mp = media_page
        self.player = media_page.player
        self.setFixedHeight(85)
        self.setObjectName("AuthCard")
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)
        
        l = QHBoxLayout(self)
        l.setContentsMargins(15, 5, 20, 5)
        l.setSpacing(20)
        
        self.vinyl = VinylWidget(size=60)
        
        meta = QVBoxLayout()
        meta.setSpacing(2)
        meta.setAlignment(Qt.AlignVCenter)
        self.lbl_t = QLabel("Нет музыки")
        self.lbl_t.setObjectName("Header")
        self.lbl_t.setStyleSheet("font-size: 14px;")
        self.lbl_p = QLabel("...")
        self.lbl_p.setObjectName("SubTitle")
        meta.addWidget(self.lbl_t)
        meta.addWidget(self.lbl_p)
        
        self.btn = QPushButton("▶")
        self.btn.setFixedSize(44, 44)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.mp.toggle_play)
        self.btn.setStyleSheet(f"background-color: {ACCENT_COLOR}; border-radius: 22px; color: white; font-size: 20px; border: none; padding-bottom: 3px;")
        
        slider_area = QVBoxLayout()
        slider_area.setAlignment(Qt.AlignVCenter)
        
        sl_h = QHBoxLayout()
        self.lc = QLabel("00:00")
        self.lc.setObjectName("SubTitle")
        self.sl = SeekSlider(Qt.Horizontal)
        self.sl.setCursor(Qt.PointingHandCursor)
        self.sl.setStyleSheet(f"""
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{ height: 4px; background: #334155; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {ACCENT_COLOR}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: white; width: 14px; margin: -5px 0; border-radius: 7px; }}
        """)
        self.lt = QLabel("00:00")
        self.lt.setObjectName("SubTitle")
        sl_h.addWidget(self.lc)
        sl_h.addWidget(self.sl)
        sl_h.addWidget(self.lt)
        
        slider_area.addLayout(sl_h)
        
        l.addWidget(self.vinyl)
        l.addWidget(self.btn)
        l.addLayout(meta)
        l.addLayout(slider_area)
        l.addSpacing(10)
        
        self.btn_m = QPushButton("🔊")
        self.btn_m.setFlat(True)
        self.btn_m.clicked.connect(self.t_mute)
        self.btn_m.setStyleSheet("background: transparent; border: none;")
        
        self.v = SeekSlider(Qt.Horizontal)
        self.v.setFixedWidth(80)
        self.v.setValue(50)
        self.v.valueChanged.connect(self.s_vol)
        self.v.setStyleSheet(self.sl.styleSheet())
        
        l.addWidget(self.btn_m)
        l.addWidget(self.v)
        
        self.sl.sliderMoved.connect(self.on_seek_move)
        self.sl.sliderReleased.connect(self.on_seek_release)
        
        self.is_dragging = False
        self.dur = 0
        self.prev_vol = 50
        self.is_m = False
    
    def on_seek_move(self, val):
        self.is_dragging = True
        self.lc.setText(self.f_t(val))
        if self.dur > 0:
            self.vinyl.set_progress(val, self.dur)
    
    def on_seek_release(self):
        val = self.sl.value()
        self.mp.player.setPosition(val)
        self.is_dragging = False
    
    def update_state(self):
        state = self.player.playbackState()
        play = (state == QMediaPlayer.PlayingState)
        self.btn.setText("⏸" if play else "▶")
        self.vinyl.set_playing(play)
        if play or self.player.mediaStatus() == QMediaPlayer.BufferedMedia:
            self.dur = self.player.duration()
            self.sl.setMaximum(self.dur)
            pos = self.player.position()
            if not self.is_dragging:
                self.sl.setValue(pos)
                self.lc.setText(self.f_t(pos))
            self.lt.setText(self.f_t(self.dur))
            self.vinyl.set_progress(pos, self.dur)
        self.mp.propagate_state(play)
    
    def f_t(self, m):
        return f"{(m // 60000):02d}:{(m // 1000) % 60:02d}"
    
    def s_vol(self, v):
        self.mp.audio_out.setVolume(v / 100)
        if v > 0:
            self.is_m = False
            self.btn_m.setText("🔊")
        else:
            self.is_m = True
            self.btn_m.setText("🔇")
    
    def t_mute(self):
        if not self.is_m:
            self.prev_vol = self.v.value()
            self.v.setValue(0)
        else:
            self.v.setValue(self.prev_vol or 20)
    
    def set_meta(self, t, p, cp):
        self.lbl_t.setText(t)
        self.lbl_p.setText(p)
        if cp and os.path.exists(cp):
            self.vinyl.cover_pixmap = QPixmap(cp)
        else:
            self.vinyl.cover_pixmap = None
        self.vinyl.update()

class MediaPage(QWidget):
    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(0.5)
        self.active_group = None
        self.current_album_tracks = []
        self.tracks_cache = {}
        self.ccp = None
        self.current_play_path = None
        self.current_user = None
        self.w_g = None # IMPORTANT: Init worker var
        
        self.setup_ui()
        
        self.timer_p = QTimer(self)
        self.timer_p.timeout.connect(self.player_ui.update_state)
        self.timer_p.start(100)

    def stop_all_workers(self):
        # Остановить все активные потоки
        if hasattr(self, 'w_g') and self.w_g and self.w_g.isRunning():
            self.w_g.stop()
            self.w_g.quit()
            self.w_g.wait()
            self.w_g.deleteLater()
            self.w_g = None
        
        # Остановить другие возможные потоки
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, QThread) and attr.isRunning():
                attr.quit()

    def set_user(self, u):
        self.stop_all_workers()  # Останавливаем старые потоки
        self.current_user = u
        self.refresh_groups()
    
    def setup_ui(self):
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        
        self.top_bar = QFrame()
        self.top_bar.setObjectName("AuthCard")
        self.top_bar.setFixedHeight(60)
        
        th = QHBoxLayout(self.top_bar)
        th.setContentsMargins(10, 5, 10, 5)
        th.setSpacing(20)
        
        self.bt_m = self.tab("Альбомы", True, 0)
        self.bt_v = self.tab("Видео", False, 1)
        self.bt_b = self.tab("Загрузчик", False, 2)
        
        th.addStretch()
        th.addWidget(self.bt_m)
        th.addWidget(self.bt_v)
        th.addWidget(self.bt_b)
        th.addStretch()
        
        self.stack = QStackedWidget()
        
        self.pg_m = QWidget()
        ml = QVBoxLayout(self.pg_m)
        ml.setContentsMargins(0, 0, 0, 0)
        
        ctrl = QHBoxLayout()
        self.se = QLineEdit()
        self.se.setPlaceholderText("🔍 Поиск альбомов...")
        self.se.textChanged.connect(self.flt_grp)
        self.se.setFixedHeight(40)
        
        ba = QPushButton(" + Альбом")
        ba.setObjectName("PrimaryBtn")
        ba.setFixedHeight(40)
        ba.clicked.connect(self.add_grp)
        
        ctrl.addWidget(self.se)
        ctrl.addWidget(ba)
        ml.addLayout(ctrl)
        
        self.sa = QScrollArea()
        self.sa.setWidgetResizable(True)
        self.sa.setStyleSheet("background: transparent; border: none;")
        self.gw = QWidget()
        self.grid = QGridLayout(self.gw)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid.setSpacing(20)
        self.sa.setWidget(self.gw)
        ml.addWidget(self.sa)
        
        self.pg_md = QWidget()
        dl = QVBoxLayout(self.pg_md)
        dh = QHBoxLayout()
        
        bb = QPushButton("Назад")
        bb.setObjectName("NavBtn")
        bb.setFixedSize(100, 36)
        bb.setStyleSheet("border: 1px solid #777; border-radius: 8px;")
        bb.setCursor(Qt.PointingHandCursor)
        bb.clicked.connect(self.cls_det)
        
        self.lbl_grp_name = QLabel("")
        self.lbl_grp_name.setObjectName("Header")
        
        bat = QPushButton("+ Трек")
        bat.setObjectName("PrimaryBtn")
        bat.setFixedSize(100, 36)
        bat.clicked.connect(self.add_trk)
        
        dh.addWidget(bb)
        dh.addWidget(self.lbl_grp_name)
        dh.addStretch()
        dh.addWidget(bat)
        dl.addLayout(dh)
        
        self.scroll_tracks = QScrollArea()
        self.scroll_tracks.setWidgetResizable(True)
        self.scroll_tracks.setStyleSheet("background: transparent; border: none;")
        self.tr_w = QWidget()
        self.tr_l = QVBoxLayout(self.tr_w)
        self.tr_l.setAlignment(Qt.AlignTop)
        self.scroll_tracks.setWidget(self.tr_w)
        dl.addWidget(self.scroll_tracks)
        
        self.mus_stack = QStackedWidget()
        self.mus_stack.addWidget(self.pg_m)
        self.mus_stack.addWidget(self.pg_md)
        
        self.pg_v = self.construction_page()
        self.pg_b = self.construction_page()
        
        self.stack.addWidget(self.mus_stack)
        self.stack.addWidget(self.pg_v)
        self.stack.addWidget(self.pg_b)
        
        l.addWidget(self.top_bar)
        l.addWidget(self.stack)
        
        self.player_ui = PlayerWidget(self)
        l.addWidget(self.player_ui)
    
    def construction_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        l = QLabel("В стадии разработки")
        l.setAlignment(Qt.AlignCenter)
        l.setObjectName("Header")
        l.setStyleSheet("font-size: 24px; color: #777;")
        v.addWidget(l)
        return w
    
    def tab(self, name, active, idx):
        b = QPushButton(name)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(140, 40)
        if active:
            b.setObjectName("PrimaryBtn")
        else:
            b.setObjectName("NavBtn")
            b.setStyleSheet("border: none;")
        b.clicked.connect(lambda: self.switch_tab(idx))
        return b
    
    def switch_tab(self, i):
        self.stack.setCurrentIndex(i)
        for k, b in enumerate([self.bt_m, self.bt_v, self.bt_b]):
            if k == i:
                b.setObjectName("PrimaryBtn")
                b.setStyleSheet("")
            else:
                b.setObjectName("NavBtn")
                b.setStyleSheet("border: none;")
        if i == 0:
            self.refresh_groups()
    
    def refresh_groups(self):
        if not self.current_user:
            return
        
        # Защита от дублирования потоков (Prevents crashing!)
        if self.w_g and self.w_g.isRunning():
            return
            
        self.w_g = APIWorker("/media/groups", {"username": self.current_user})
        self.w_g.setParent(self) # Can set explicitly
        self.w_g.finished.connect(self.got_groups)
        self.w_g.start()
    
    def got_groups(self, r):
        if not r:
            return
        self.all_grp = r.get('groups', [])
        self.flt_grp("")
    
    def flt_grp(self, t):
        if hasattr(self, 'all_grp'):
            fs = [g for g in self.all_grp if t.lower() in g['title'].lower()]
            
            while self.grid.count():
                item = self.grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            r, c = 0, 0
            for g in fs:
                fr = QFrame()
                fr.setFixedSize(180, 240)
                fr.setCursor(Qt.PointingHandCursor)
                fr.setObjectName("AuthCard")
                fr.data_ref = g
                
                fr.setStyleSheet("QFrame#AuthCard { border: 1px solid rgba(127,127,127,0.3); border-radius: 12px; } QFrame#AuthCard:hover { border: 1px solid #6366f1; }")
                
                fr_l = QVBoxLayout(fr)
                fr_l.setContentsMargins(10, 10, 10, 10)
                fr_l.setSpacing(5)
                
                pic = QLabel("💿")
                pic.setAlignment(Qt.AlignCenter)
                pic.setStyleSheet("background: #111; border-radius: 8px; font-size: 40px; color: #fff;")
                pic.setFixedHeight(140)
                
                if g['cover_path'] and os.path.exists(g['cover_path']):
                    pic.setPixmap(QPixmap(g['cover_path']).scaled(160, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    pic.setText("")
                
                nm = QLabel(g['title'])
                nm.setObjectName("Header")
                nm.setStyleSheet("font-size: 13px; background: transparent; border: none;")
                nm.setWordWrap(True)
                
                au = QLabel(g['author'])
                au.setObjectName("SubTitle")
                au.setStyleSheet("background: transparent; border: none;")
                
                fr_l.addWidget(pic)
                fr_l.addWidget(nm)
                fr_l.addWidget(au)
                
                fr.setContextMenuPolicy(Qt.CustomContextMenu)
                fr.customContextMenuRequested.connect(lambda p, widget=fr, d=g: self.ctx_group(p, widget, d))
                
                btn = QPushButton(fr)
                btn.setFixedSize(180, 240)
                btn.setStyleSheet("background: transparent; border: none;")
                btn.clicked.connect(lambda checked, gid=g['id'], tit=g['title']: self.opn_det(gid, tit))
                
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(lambda p, widget=fr, d=g: self.ctx_group(p, widget, d))
                
                self.grid.addWidget(fr, r, c)
                c += 1
                if c > 4:
                    c = 0
                    r += 1
    
    def ctx_group(self, pos, widget, data):
        menu = QMenu(widget)
        menu.setStyleSheet(MENU_STYLE)
        a_ed = menu.addAction("Редактировать")
        a_del = menu.addAction("Удалить")
        res = menu.exec(widget.mapToGlobal(pos))
        if res == a_del:
            self.delete_grp(data)
        elif res == a_ed:
            self.edit_grp(data)
    
    def edit_grp(self, d):
        dlg = GroupDialog(mode="edit", data=d, parent=self)
        if dlg.exec():
            self.api = APIWorker("/media/group/update", {"id": d['id'], "title": dlg.inp_title.text(),
                                                        "author": dlg.inp_author.text(), "genre": dlg.inp_genre.text(),
                                                        "cover_path": dlg.cover_path}, "PUT")
            self.api.setParent(self)
            self.api.finished.connect(lambda x: self.refresh_groups())
            self.api.start()
    
    def delete_grp(self, d):
        if QMessageBox.question(self, "?", f"Удалить {d['title']}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.api = APIWorker("/media/group/delete", {"id": d['id']}, "DELETE")
            self.api.setParent(self)
            self.api.finished.connect(lambda x: self.refresh_groups())
            self.api.start()
    
    def add_grp(self):
        d = GroupDialog(mode="add", parent=self)
        if d.exec():
            payload = {
                "username": self.current_user,
                "title": d.inp_title.text(), 
                "author": d.inp_author.text(),
                "genre": d.inp_genre.text(), 
                "cover_path": d.cover_path
            }
            self.w_add_g = APIWorker("/media/group", payload, "POST")
            self.w_add_g.setParent(self)
            self.w_add_g.finished.connect(lambda x: self.refresh_groups())
            self.w_add_g.start()
    
    def opn_det(self, gid, title):
        self.active_group = gid
        self.lbl_grp_name.setText(title)
        self.ccp = next((g.get('cover_path') for g in self.all_grp if g['id'] == gid), None)
        
        while self.tr_l.count():
            item = self.tr_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.mus_stack.setCurrentIndex(1)
        
        if gid in self.tracks_cache:
            self.render_tracks(self.tracks_cache[gid])
        else:
            self.refresh_tracks()
    
    def cls_det(self):
        self.active_group = None
        self.mus_stack.setCurrentIndex(0)
    
    def refresh_tracks(self):
        if not self.active_group:
            return
        self.w_tr = APIWorker("/media/tracks", {"group_id": self.active_group})
        self.w_tr.setParent(self)
        self.w_tr.finished.connect(self.on_tracks_loaded)
        self.w_tr.start()
    
    def on_tracks_loaded(self, res):
        if not res:
            return
        self.tracks_cache[self.active_group] = res
        self.render_tracks(res)
    
    def render_tracks(self, res):
        if not res:
            return
        
        while self.tr_l.count():
            item = self.tr_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.scroll_tracks.verticalScrollBar().setValue(0)
        self.current_album_tracks = res.get('tracks', [])
        
        originals_map = {}
        covers_list = []
        for t in self.current_album_tracks:
            if t['is_original']:
                originals_map[t['id']] = {"data": t, "covers": []}
            else:
                covers_list.append(t)
        
        orphans = []
        for c in covers_list:
            pid = c.get('parent_id')
            if pid and pid in originals_map:
                originals_map[pid]["covers"].append(c)
            else:
                orphans.append(c)
        
        for oid, bundle in originals_map.items():
            node = TreeTrackWidget(bundle['data'], bundle['covers'])
            node.play_signal_propagate.connect(lambda f, t, p, _=None: self.play_media(f, t, p))
            node.edit_signal.connect(self.edit_track)
            node.delete_signal.connect(self.delete_track)
            self.tr_l.addWidget(node)
        
        if orphans:
            lbl = QLabel("Unlinked")
            lbl.setObjectName("SubTitle")
            self.tr_l.addWidget(lbl)
            for c in orphans:
                row = TrackRowWidget(c, is_cover=False)
                row.play_requested.connect(lambda f, t, p, _=None: self.play_media(f, t, p))
                row.edit_requested.connect(self.edit_track)
                row.delete_requested.connect(self.delete_track)
                self.tr_l.addWidget(row)
        
        self.tr_l.addStretch()
        self.propagate_state(self.player.playbackState() == QMediaPlayer.PlayingState)
    
    def propagate_state(self, playing):
        count = self.tr_l.count()
        for i in range(count):
            item = self.tr_l.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if hasattr(w, 'update_icon'):
                    w.update_icon(self.current_play_path, playing)
                if hasattr(w, 'update_icons'):
                    w.update_icons(self.current_play_path, playing)
    
    def edit_track(self, d):
        dlg = TrackDialog(mode="edit", data=d, group_id=self.active_group, existing_tracks=self.current_album_tracks, parent=self)
        if dlg.exec():
            dd = dlg.accept_data
            dd['id'] = d['id']
            self.w_up = APIWorker("/media/track/update", dd, "PUT")
            self.w_up.setParent(self)
            self.w_up.finished.connect(lambda x: self.force_refresh())
            self.w_up.start()
    
    def delete_track(self, d):
        if QMessageBox.question(self, "?", f"Удалить трек {d['title']}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.current_play_path == d['file_path']:
                self.player.stop()
                self.current_play_path = None
                self.player_ui.set_meta("Нет музыки", "...", None)
                self.player_ui.vinyl.set_playing(False)
                self.player_ui.vinyl.set_progress(0, 0)
            
            self.w_del = APIWorker("/media/track/delete", {"id": d['id']}, "DELETE")
            self.w_del.setParent(self)
            self.w_del.finished.connect(lambda x: self.force_refresh())
            self.w_del.start()
    
    def add_trk(self):
        d = TrackDialog(mode="add", group_id=self.active_group, existing_tracks=self.current_album_tracks, parent=self)
        if d.exec():
            d.accept_data['parent_id'] = d.accept_data.get('parent_id')
            self.w_add_t = APIWorker("/media/track", d.accept_data, "POST")
            self.w_add_t.setParent(self)
            self.w_add_t.finished.connect(lambda x: self.force_refresh())
            self.w_add_t.start()
    
    def force_refresh(self):
        if self.active_group in self.tracks_cache:
            del self.tracks_cache[self.active_group]
        self.refresh_tracks()
    
    def play_media(self, path, title, performer=""):
        if not os.path.exists(path):
            QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{path}")
            return
        
        if self.current_play_path == path:
            if self.player.playbackState() == QMediaPlayer.PlayingState:
                self.player.pause()
            else:
                self.player.play()
            return
        
        self.player.stop()
        self.current_play_path = path
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self.player_ui.set_meta(title, performer, self.ccp)
        self.propagate_state(True)
    
    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()