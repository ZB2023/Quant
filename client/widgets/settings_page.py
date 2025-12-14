import requests
import urllib3
import os
import io
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialog, QLineEdit, QFrame,
    QGraphicsDropShadowEffect, QFileDialog, QGraphicsView,
    QGraphicsScene, QGraphicsPixmapItem, QSlider, QGraphicsObject
)
from PySide6.QtCore import Qt, Signal, QThread, QPoint, QBuffer, QIODevice, QByteArray, QRectF
from PySide6.QtGui import QColor, QPixmap, QPainter, QPainterPath, QPen, QMovie

try:
    from PIL import Image, ImageSequence
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

urllib3.disable_warnings()
API_URL = "https://localhost:8001"

class UpWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, u, path=None, data=None, rem=False, crop_data=None):
        super().__init__()
        self.u = u
        self.path = path
        self.data = data
        self.rem = rem
        self.crop_data = crop_data

    def run(self):
        try:
            timeout = 120
            if self.rem:
                r = requests.post(f"{API_URL}/user/avatar/delete", json={"username": self.u}, verify=False, timeout=10)
            elif self.path and self.crop_data and self.path.lower().endswith('.gif') and HAS_PIL:
                try:
                    x, y, w, h = self.crop_data
                    with Image.open(self.path) as im:
                        frames = []
                        duration = im.info.get('duration', 100)
                        for frame in ImageSequence.Iterator(im):
                            cropped = frame.crop((x, y, x + w, y + h))
                            cropped = cropped.resize((500, 500), Image.LANCZOS)
                            frames.append(cropped)
                        b_io = io.BytesIO()
                        if frames:
                            frames[0].save(
                                b_io,
                                format="GIF",
                                save_all=True,
                                append_images=frames[1:],
                                loop=0,
                                duration=duration,
                                disposal=2
                            )
                        final_bytes = b_io.getvalue()
                        r = requests.post(
                            f"{API_URL}/user/avatar/upload",
                            data={'username': self.u},
                            files={'file': ("avatar.gif", final_bytes, 'image/gif')},
                            verify=False,
                            timeout=timeout
                        )
                except Exception as ex:
                    self.done.emit(False, str(ex))
                    return
            elif self.path:
                with open(self.path, 'rb') as f:
                    r = requests.post(f"{API_URL}/user/avatar/upload", data={'username': self.u},
                                      files={'file': (os.path.basename(self.path), f.read(), 'image/*')},
                                      verify=False, timeout=timeout)
            else:
                r = requests.post(f"{API_URL}/user/avatar/upload", data={'username': self.u},
                                  files={'file': ("avatar.png", self.data, 'image/png')}, verify=False, timeout=30)

            if r.status_code == 200:
                self.done.emit(True, "OK")
            else:
                self.done.emit(False, str(r.status_code))
        except Exception as e:
            self.done.emit(False, str(e))

class AuthW(QThread):
    res = Signal(bool, str)

    def __init__(self, l, p):
        super().__init__()
        self.l = l
        self.p = p

    def run(self):
        try:
            r = requests.post(f"{API_URL}/login", json={"login": self.l, "pw": self.p}, verify=False, timeout=5)
            if r.status_code == 200:
                self.res.emit(True, self.l)
            else:
                self.res.emit(False, "Ошибка входа")
        except:
            self.res.emit(False, "Ошибка сети")

class DelW(QThread):
    res = Signal(bool, str)

    def __init__(self, u, p):
        super().__init__()
        self.u = u
        self.p = p

    def run(self):
        try:
            r = requests.delete(f"{API_URL}/user/delete", json={"username": self.u, "pw": self.p}, verify=False, timeout=10)
            if r.status_code == 200:
                self.res.emit(True, "OK")
            else:
                self.res.emit(False, "Неверный пароль")
        except:
            self.res.emit(False, "Ошибка сети")

class GifItem(QGraphicsObject):
    def __init__(self, path):
        super().__init__()
        self.movie = QMovie(path)
        self.movie.frameChanged.connect(self.handle_frame)
        self.movie.start()
        self.current_pix = self.movie.currentPixmap()

    def handle_frame(self):
        self.current_pix = self.movie.currentPixmap()
        self.update()

    def boundingRect(self):
        if self.current_pix.isNull():
            return QRectF()
        return QRectF(self.current_pix.rect())

    def paint(self, painter, option, widget):
        if not self.current_pix.isNull():
            painter.drawPixmap(0, 0, self.current_pix)

class CropView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.sz = 500
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setBackgroundBrush(Qt.NoBrush)
        self.setStyleSheet("background: transparent; border: none;")
        self.content_item = None
        self.pm_w = 0
        self.pm_h = 0

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def load_media(self, path):
        self.scene_obj.clear()

        if path.lower().endswith('.gif'):
            self.content_item = GifItem(path)
            s = self.content_item.boundingRect().size()
            if s.isEmpty():
                s = QPixmap(path).size()
            self.pm_w, self.pm_h = s.width(), s.height()
        else:
            pm = QPixmap(path)
            self.content_item = QGraphicsPixmapItem(pm)
            self.content_item.setTransformationMode(Qt.SmoothTransformation)
            self.pm_w, self.pm_h = pm.width(), pm.height()

        self.scene_obj.addItem(self.content_item)
        margin = 5000
        self.scene_obj.setSceneRect(-margin, -margin, self.pm_w + 2 * margin, self.pm_h + 2 * margin)

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        if e.buttons() & Qt.LeftButton:
            self.ensure_bounds()

    def wheelEvent(self, e):
        e.ignore()

    def ensure_bounds(self):
        s = self.transform().m11()
        if s <= 0: return

        r_vp = min(self.viewport().width(), self.viewport().height()) * 0.4
        r_scene = r_vp / s

        cp = self.mapToScene(self.viewport().rect().center())
        cx, cy = cp.x(), cp.y()

        min_x = r_scene
        max_x = self.pm_w - r_scene
        min_y = r_scene
        max_y = self.pm_h - r_scene

        nx, ny = cx, cy
        fix = False

        if min_x > max_x:
            nx = self.pm_w / 2
            fix = True
        else:
            if cx < min_x: nx = min_x; fix = True
            elif cx > max_x: nx = max_x; fix = True

        if min_y > max_y:
            ny = self.pm_h / 2
            fix = True
        else:
            if cy < min_y: ny = min_y; fix = True
            elif cy > max_y: ny = max_y; fix = True

        if fix:
            self.centerOn(nx, ny)

    def drawForeground(self, p, r):
        vp = self.viewport()
        rd = min(vp.width(), vp.height()) * 0.4
        c = QPoint(int(vp.width() / 2), int(vp.height() / 2))
        p.resetTransform()
        path = QPainterPath()
        path.addRect(0, 0, vp.width(), vp.height())
        el = QPainterPath()
        el.addEllipse(c, rd, rd)
        p.setBrush(QColor(0, 0, 0, 160))
        p.setPen(Qt.NoPen)
        p.drawPath(path.subtracted(el))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255), 3))
        p.drawEllipse(c, int(rd), int(rd))

    def get_crop_data(self):
        self.ensure_bounds()
        s = self.transform().m11()
        if s <= 0: return (0, 0, int(self.pm_w), int(self.pm_h))

        center_scene = self.mapToScene(self.viewport().rect().center())
        r = (min(self.viewport().width(), self.viewport().height()) * 0.4) / s
        d = r * 2

        x = int(center_scene.x() - r)
        y = int(center_scene.y() - r)
        size = int(d)

        x = max(0, x)
        y = max(0, y)
        if x + size > self.pm_w: size = self.pm_w - x
        if y + size > self.pm_h: size = self.pm_h - y

        return (x, y, size, size)

    def get_snapshot(self):
        self.ensure_bounds()
        center = self.mapToScene(self.viewport().rect().center())
        s = self.transform().m11()
        r = (min(self.viewport().width(), self.viewport().height()) * 0.4) / s
        d = r * 2
        x = center.x() - r
        y = center.y() - r

        img = QPixmap(int(d), int(d))
        img.fill(Qt.transparent)
        p = QPainter(img)
        self.scene_obj.render(p, QRectF(0, 0, d, d), QRectF(x, y, d, d))
        p.end()
        return img.scaled(self.sz, self.sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def fit_image(self):
        if self.pm_w == 0 or self.pm_h == 0: return 1.0
        d_vp = min(self.viewport().width(), self.viewport().height()) * 0.8
        min_dim = min(self.pm_w, self.pm_h)
        return d_vp / min_dim

class BDialog(QDialog):
    def __init__(self, p=None):
        super().__init__(p)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.d = False
        self.c = QFrame(self)
        self.c.setObjectName("AuthCard")
        s = QGraphicsDropShadowEffect(self)
        s.setBlurRadius(20)
        s.setColor(QColor(0, 0, 0, 80))
        self.c.setGraphicsEffect(s)
        self.l = QVBoxLayout(self)
        self.l.addWidget(self.c)
        self.cl = QVBoxLayout(self.c)
        self.cl.setSpacing(15)
        self.cl.setContentsMargins(30, 30, 30, 30)

    def head(self, t):
        h = QHBoxLayout()
        l = QLabel(t)
        l.setStyleSheet("font-size:20px; font-weight:bold;")
        l.setObjectName("Header")
        x = QPushButton("✕")
        x.clicked.connect(self.reject)
        x.setStyleSheet("border:none; color:#777; font-size:16px;")
        h.addWidget(l)
        h.addStretch()
        h.addWidget(x)
        self.cl.addLayout(h)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.d = True
            self.dp = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.d:
            self.move(e.globalPosition().toPoint() - self.dp)

    def mouseReleaseEvent(self, e):
        self.d = False

class AvDialog(BDialog):
    upd = Signal()

    def __init__(self, u, p=None):
        super().__init__(p)
        self.resize(550, 750)
        self.u = u
        self.head("Редактор Аватара")

        h = QHBoxLayout()
        bf = QPushButton("📂 Файл")
        bf.setObjectName("ThemeCard")
        bf.setCursor(Qt.PointingHandCursor)
        bf.clicked.connect(self.pick)
        bf.setFixedHeight(40)
        bd = QPushButton("🗑 Удалить")
        bd.setCursor(Qt.PointingHandCursor)
        bd.setStyleSheet("QPushButton{color:#ef4444; border:1px solid #ef4444; border-radius:10px; background:transparent} QPushButton:hover{background:rgba(239, 68, 68, 0.1);}")
        bd.clicked.connect(self.rem)
        bd.setFixedHeight(40)
        h.addWidget(bf, 1)
        h.addWidget(bd)
        self.cl.addLayout(h)

        self.z = QFrame()
        self.z.setStyleSheet("background: transparent; border: none; border-radius:12px;")
        self.z.setFixedHeight(300)
        self.zl = QVBoxLayout(self.z)
        self.zl.setAlignment(Qt.AlignCenter)
        self.zl.setContentsMargins(0, 0, 0, 0)
        self.cl.addWidget(self.z)

        self.cr = CropView()
        self.zl.addWidget(self.cr)

        self.sl = QSlider(Qt.Horizontal)
        self.sl.setRange(0, 1000)
        self.sl.setValue(0)
        self.sl.valueChanged.connect(self.on_zoom)
        self.sl.setFixedHeight(30)
        self.sl.setStyleSheet("""
            QSlider { background: transparent; }
            QSlider::groove:horizontal { border: 1px solid transparent; height: 4px; background: #475569; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #6366f1; border-radius: 2px; }
            QSlider::handle:horizontal { background: white; width: 16px; margin: -6px 0; border-radius: 8px; }
        """)
        self.cl.addWidget(self.sl)

        row_opts = QHBoxLayout()
        row_opts.setAlignment(Qt.AlignLeft)
        l_g = QLabel("GIF (Весь кадр):")
        l_g.setStyleSheet("color:#94a3b8; margin-right:10px;")
        self.ck = QPushButton("🎬")
        self.ck.setCheckable(True)
        self.ck.setCursor(Qt.PointingHandCursor)
        self.ck.setFixedSize(40, 36)
        self.ck.setStyleSheet("""
            QPushButton { border: 1px solid #475569; border-radius: 8px; background: transparent; font-size: 16px; }
            QPushButton:checked { background: #22c55e; border-color: #22c55e; color: white; }
        """)
        row_opts.addWidget(l_g)
        row_opts.addWidget(self.ck)
        row_opts.addStretch()
        self.cl.addLayout(row_opts)

        row_act = QHBoxLayout()
        bc = QPushButton("Отмена")
        bc.setFixedHeight(40)
        bc.setCursor(Qt.PointingHandCursor)
        bc.clicked.connect(self.reject)
        bc.setStyleSheet("QPushButton { border: 1px solid #475569; color: #94a3b8; border-radius: 8px; background: transparent; } QPushButton:hover { border: 1px solid white; color: white; }")

        self.sb = QPushButton("Сохранить")
        self.sb.setObjectName("PrimaryBtn")
        self.sb.setCursor(Qt.PointingHandCursor)
        self.sb.clicked.connect(self.sv)
        self.sb.setEnabled(False)
        self.sb.setFixedHeight(40)

        row_act.addWidget(bc)
        row_act.addWidget(self.sb)
        self.cl.addLayout(row_act)

        self.inf = QLabel("")
        self.inf.setAlignment(Qt.AlignCenter)
        self.inf.setStyleSheet("color:#94a3b8; font-size:12px; margin-top:5px;")
        self.cl.addWidget(self.inf)

        self.worker = None
        self.fp = None
        self.min_scale = 1.0
        self.max_scale = 5.0

    def pick(self):
        f, _ = QFileDialog.getOpenFileName(self, "Аватар", "", "Images (*.png *.jpg *.jpeg *.gif)")
        if f:
            self.fp = f
            self.inf.setText(os.path.basename(f))
            self.ld(f)

    def clr(self):
        self.cr.scene_obj.clear()

    def ld(self, p):
        self.clr()
        is_g = p.lower().endswith('.gif')
        self.ck.blockSignals(True)
        self.ck.setChecked(is_g)
        self.ck.blockSignals(False)
        self.sb.setEnabled(True)

        self.cr.load_media(p)
        self.min_scale = self.cr.fit_image()
        self.max_scale = self.min_scale * 5.0

        self.sl.blockSignals(True)
        self.sl.setValue(0)
        self.sl.blockSignals(False)

        self.cr.resetTransform()
        self.cr.scale(self.min_scale, self.min_scale)
        self.cr.centerOn(self.cr.pm_w / 2, self.cr.pm_h / 2)

    def on_zoom(self, v):
        t = v / 1000.0
        ns = self.min_scale + t * (self.max_scale - self.min_scale)
        self.cr.resetTransform()
        self.cr.scale(ns, ns)
        self.cr.ensure_bounds()

    def tg(self, c):
        if self.fp:
            self.ld(self.fp)
            self.ck.blockSignals(True)
            self.ck.setChecked(c)
            self.ck.blockSignals(False)

    def sv(self):
        self.inf.setText("Сохранение...")
        self.inf.setStyleSheet("color:#6366f1")
        self.sb.setEnabled(False)

        crop_params = None
        is_gif_file = self.fp and self.fp.lower().endswith('.gif')

        if is_gif_file and not self.ck.isChecked():
            crop_params = self.cr.get_crop_data()
            self.worker = UpWorker(self.u, path=self.fp, crop_data=crop_params)
        elif self.ck.isChecked():
            self.worker = UpWorker(self.u, path=self.fp)
        else:
            i = self.cr.get_snapshot()
            b = QByteArray()
            q = QBuffer(b)
            q.open(QIODevice.WriteOnly)
            i.save(q, "PNG")
            self.worker = UpWorker(self.u, data=b.data())

        self.worker.done.connect(self.fin)
        self.worker.start()

    def rem(self):
        self.inf.setText("Удаление...")
        self.inf.setStyleSheet("color:#ef4444")
        self.sb.setEnabled(False)
        self.worker = UpWorker(self.u, rem=True)
        self.worker.done.connect(self.fin)
        self.worker.start()

    def fin(self, ok, msg):
        self.sb.setEnabled(True)
        if ok:
            self.inf.setText("Успешно!")
            self.inf.setStyleSheet("color:#22c55e")
            self.upd.emit()
            self.accept()
        else:
            self.inf.setText(f"Ошибка: {msg}")
            self.inf.setStyleSheet("color:#ef4444")

class EdDialog(BDialog):
    def __init__(self, u, s, b, p=None):
        super().__init__(p)
        self.resize(400, 350)
        self.head("Ред. профиль")
        self.u = u
        self.is_ = QLineEdit(s)
        self.is_.setPlaceholderText("Статус")
        self.ib = QLineEdit(b)
        self.ib.setPlaceholderText("О себе")
        self.cl.addWidget(QLabel("Статус:", objectName="SubTitle"))
        self.cl.addWidget(self.is_)
        self.cl.addWidget(QLabel("Био:", objectName="SubTitle"))
        self.cl.addWidget(self.ib)
        self.st = QLabel("")
        self.st.setAlignment(Qt.AlignCenter)
        self.st.setStyleSheet("font-size:12px; margin:5px;")
        self.cl.addWidget(self.st)
        bn = QPushButton("Сохранить")
        bn.setObjectName("PrimaryBtn")
        bn.setCursor(Qt.PointingHandCursor)
        bn.clicked.connect(self.sv)
        self.cl.addWidget(bn)
        self.cl.addStretch()

    def sv(self):
        self.st.setText("Сохранение...")
        self.st.setStyleSheet("color:#6366f1")
        try:
            r = requests.post(f"{API_URL}/user/profile_update",
                              json={"username": self.u, "status_msg": self.is_.text(), "bio": self.ib.text()},
                              verify=False)
            if r.status_code == 200:
                self.accept()
            else:
                self.st.setText("Ошибка сервера")
                self.st.setStyleSheet("color:#ef4444")
        except:
            self.st.setText("Нет соединения")
            self.st.setStyleSheet("color:#ef4444")

class SwDialog(BDialog):
    suc = Signal(str)

    def __init__(self, p=None):
        super().__init__(p)
        self.resize(350, 320)
        self.head("Вход")
        self.ul = QLineEdit()
        self.ul.setPlaceholderText("Логин")
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw.setPlaceholderText("Пароль")
        self.cl.addWidget(self.ul)
        self.cl.addWidget(self.pw)
        self.inf = QLabel("Введите данные")
        self.inf.setAlignment(Qt.AlignCenter)
        self.inf.setStyleSheet("color:#64748b; font-size:12px;")
        self.cl.addWidget(self.inf)
        self.bn = QPushButton("Войти")
        self.bn.setObjectName("PrimaryBtn")
        self.bn.clicked.connect(self.go)
        self.cl.addWidget(self.bn)
        self.cl.addStretch()
        self.w = None
        self.pending_login = None 

    def go(self):
        self.inf.setText("Вход...")
        self.inf.setStyleSheet("color:#6366f1")
        self.bn.setEnabled(False) # Блок кнопки
        
        # Создаем поток авторизации БЕЗ родителя (self), чтобы GC не убил его вместе с диалогом
        self.w = AuthW(self.ul.text(), self.pw.text())
        self.w.res.connect(self.fin)
        self.w.start()

    def fin(self, o, m):
        # Безопасно завершаем поток
        if self.w:
            self.w.quit()
            self.w.wait()
        
        self.bn.setEnabled(True)
        if o:
            self.pending_login = m
            self.accept() # Просто закрываем, сигнал отправим снаружи
        else:
            self.inf.setText(m)
            self.inf.setStyleSheet("color:#ef4444")
            self.w = None # Сброс ссылки

    def closeEvent(self, e):
        # Гарантированная остановка потока
        if self.w and self.w.isRunning():
            self.w.res.disconnect() # Отцепляем сигнал, чтобы не крашнуло при ответе в мертвый диалог
            self.w.quit()
            self.w.wait() # Ждем завершения
        super().closeEvent(e)

class DelDialog(BDialog):
    cf = Signal(str)

    def __init__(self, u, p=None):
        super().__init__(p)
        self.u = u
        self.resize(350, 280)
        self.head("Удаление")
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw.setPlaceholderText("Пароль")
        self.cl.addWidget(QLabel("Введите пароль:", objectName="SubTitle"))
        self.cl.addWidget(self.pw)
        self.inf = QLabel("Действие необратимо!")
        self.inf.setAlignment(Qt.AlignCenter)
        self.inf.setStyleSheet("color:#f59e0b; font-size:12px; font-weight:bold; margin:5px;")
        self.cl.addWidget(self.inf)
        bn = QPushButton("ПОДТВЕРДИТЬ")
        bn.setCursor(Qt.PointingHandCursor)
        bn.setStyleSheet("background:#ef4444; color:white; font-weight:bold; border-radius:8px; padding:10px;")
        bn.clicked.connect(self.go)
        self.cl.addWidget(bn)
        self.cl.addStretch()
        self.w = None

    def go(self):
        self.inf.setText("Обработка...")
        self.inf.setStyleSheet("color:#6366f1")
        self.w = DelW(self.u, self.pw.text())
        self.w.res.connect(self.fin)
        self.w.start()

    def fin(self, ok, msg):
        if ok:
            self.cf.emit(self.pw.text())
            self.accept()
        else:
            self.inf.setText(msg)
            self.inf.setStyleSheet("color:#ef4444")

class SettingsPage(QWidget):
    avatar_changed = Signal()
    profile_changed = Signal()
    out = Signal()
    sw = Signal(str)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.tm = theme_manager
        self.u = None
        self.active_mode = "dark"
        self.mode_btns = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 40)
        main_layout.setSpacing(25)

        lbl_h = QLabel("Настройки")
        lbl_h.setObjectName("Header")
        lbl_h.setStyleSheet("font-size:28px; font-weight:800; border:none; margin-bottom:10px;")
        main_layout.addWidget(lbl_h)

        fr1 = QFrame()
        fr1.setObjectName("AuthCard")
        l1 = QVBoxLayout(fr1)
        l1.setContentsMargins(20, 20, 20, 20)
        self.in_head(l1, "Внешний вид")
        cnt1 = QWidget()
        cnt1.setStyleSheet("background:transparent; border:none")
        l_col = QHBoxLayout(cnt1)
        l_col.setAlignment(Qt.AlignLeft)
        l_col.setContentsMargins(0, 0, 0, 0)
        for c in ["#6366f1", "#2563eb", "#16a34a", "#facc15", "#dc2626", "#06b6d4"]:
            b = QPushButton()
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(36, 36)
            b.setObjectName("ColorBtn")
            b.setStyleSheet(f"QPushButton {{ background:{c}; border-radius:18px; border:2px solid #334155; }} QPushButton:hover {{ border:2px solid white; }}")
            b.clicked.connect(lambda _, x=c: self.tm.apply_theme(accent=x))
            l_col.addWidget(b)
        l1.addWidget(cnt1)
        main_layout.addWidget(fr1)

        fr2 = QFrame()
        fr2.setObjectName("AuthCard")
        l2 = QVBoxLayout(fr2)
        l2.setContentsMargins(20, 20, 20, 20)
        self.in_head(l2, "Режим")
        cnt2 = QWidget()
        cnt2.setStyleSheet("background:transparent; border:none")
        l_mod = QHBoxLayout(cnt2)
        l_mod.setAlignment(Qt.AlignLeft)
        l_mod.setContentsMargins(0, 0, 0, 0)
        for n, k in [("Тёмная", "dark"), ("Светлая", "light"), ("Контраст", "high_contrast")]:
            b = QPushButton(n)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(110, 42)
            b.clicked.connect(lambda _, x=k: self.apply_mode(x))
            self.mode_btns[k] = b
            l_mod.addWidget(b)
        l2.addWidget(cnt2)
        main_layout.addWidget(fr2)
        self.update_mode_style()

        fr3 = QFrame()
        fr3.setObjectName("AuthCard")
        l3 = QVBoxLayout(fr3)
        l3.setContentsMargins(20, 20, 20, 20)
        self.in_head(l3, "Управление аккаунтом")
        cnt3 = QWidget()
        cnt3.setStyleSheet("background:transparent; border:none")
        l_acc = QHBoxLayout(cnt3)
        l_acc.setContentsMargins(0, 0, 0, 0)

        self.b_av = self.mk_btn("Аватар", "#6366f1", self.c_av)
        self.b_pr = self.mk_btn("Профиль", "#8b5cf6", self.c_pr)
        self.b_sw = self.mk_btn("Сменить", "#94a3b8", self.c_sw)

        self.b_out = QPushButton("Выйти")
        self.b_out.setFixedSize(100, 42)
        self.b_out.setCursor(Qt.PointingHandCursor)
        self.b_out.setStyleSheet("""
            QPushButton { border: 2px solid #ef4444; color: #ef4444; background: transparent; border-radius: 10px; font-weight: bold; }
            QPushButton:hover { background: #ef4444; color: white; }
            QPushButton:pressed { background: #dc2626; }
        """)
        self.b_out.clicked.connect(self.out.emit)

        self.b_del = self.mk_btn("Удалить", "#f87171", self.c_dl)
        l_acc.addWidget(self.b_av)
        l_acc.addWidget(self.b_pr)
        l_acc.addWidget(self.b_sw)
        l_acc.addWidget(self.b_out)
        l_acc.addWidget(self.b_del)
        l_acc.addStretch()
        l3.addWidget(cnt3)
        main_layout.addWidget(fr3)
        main_layout.addStretch()

    def apply_mode(self, m):
        self.active_mode = m
        self.tm.apply_theme(mode=m)
        self.update_mode_style()

    def update_mode_style(self):
        is_light = (self.active_mode == "light")
        bg_in = "#ffffff" if is_light else "#1e293b"
        fg_in = "#64748b" if is_light else "#94a3b8"
        br_in = "#e2e8f0" if is_light else "#334155"
        
        bg_ac = "#2563eb"
        fg_ac = "#ffffff"
        br_ac = "#2563eb"

        for k, b in self.mode_btns.items():
            if k == self.active_mode:
                b.setStyleSheet(f"QPushButton {{ background-color: {bg_ac}; color: {fg_ac}; border: 2px solid {br_ac}; border-radius: 12px; font-weight: bold; }}")
            else:
                b.setStyleSheet(f"QPushButton {{ background-color: {bg_in}; color: {fg_in}; border: 1px solid {br_in}; border-radius: 12px; }} QPushButton:hover {{ border: 1px solid {bg_ac}; color: {bg_ac}; }}")

    def in_head(self, l, t):
        lb = QLabel(t)
        lb.setObjectName("SectionTitle")
        lb.setStyleSheet("border:none; padding:0; margin-bottom:5px;")
        l.addWidget(lb)

    def mk_btn(self, t, c, slot):
        b = QPushButton(t)
        b.setFixedSize(120, 42)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        b.setStyleSheet(f"""
            QPushButton {{ border: 2px solid {c}; color: {c}; font-weight: bold; background: transparent; border-radius: 10px; }} 
            QPushButton:hover {{ background: {c}; color: white; }}
            QPushButton:pressed {{ border-color: white; }}
        """)
        return b

    def set_user(self, u):
        self.u = u

    def c_av(self):
        if self.u:
            d = AvDialog(self.u, self)
            d.upd.connect(self.avatar_changed.emit)
            d.exec()

    def c_pr(self):
        if self.u:
            try:
                r = requests.get(f"{API_URL}/user/profile_info", params={"username": self.u}, verify=False)
                if r.status_code == 200:
                    j = r.json()
                    if EdDialog(self.u, j.get("status_msg", ""), j.get("bio", ""), self).exec():
                        self.profile_changed.emit()
            except:
                pass

    def c_sw(self):
        # Передаем self.window() как родителя, чтобы диалог был модальным для всего окна, 
        # но не привязан к SettingsPage насмерть.
        d = SwDialog(self.window())
        
        # Запускаем модально
        res = d.exec()
        
        if res == QDialog.Accepted and d.pending_login:
            login = d.pending_login
            # Разрываем стек вызовов таймером. 
            # Диалог d уничтожится, управление вернется в Qt Loop, и только потом сработает эмит.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, lambda: self.sw.emit(login))

    def _safe_switch(self, login):
        # Отложенный вызов смены пользователя
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.sw.emit(login))

    def c_dl(self):
        if self.u:
            d = DelDialog(self.u, self)
            d.cf.connect(self.do_del)
            d.exec()

    def do_del(self, p):
        self.out.emit()