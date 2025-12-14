import base64
import math
import os
import datetime
from dateutil import parser as date_parser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QTextEdit,
    QGridLayout, QAbstractButton, QTextBrowser, QMenu, QStackedLayout, QApplication
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QSize, Property, QPropertyAnimation, QEasingCurve,
    QBuffer, QIODevice, QPoint, QUrl, QPointF, QRectF, QRect, QThreadPool
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath,
    QPen, QBrush, QLinearGradient, QMovie, QFontMetrics,
    QDesktopServices, QCursor, QPixmap, QConicalGradient
)
from client.widgets.messages_page.dialogs import HybridGalleryOverlay
from .cache import ImageCache
from .network import ChatImageLoader

MAX_ATTACHMENTS = 10
ATTACHMENT_SPLITTER = "<<<SPLIT>>>"

def open_local_or_remote_file(path_str):
    url = QUrl(path_str)
    if not path_str.startswith("http") and not path_str.startswith("file://"):
        if os.path.exists(path_str):
            url = QUrl.fromLocalFile(os.path.abspath(path_str))
    QDesktopServices.openUrl(url)

class DateHeaderWidget(QWidget):
    def __init__(self, date_text, parent=None):
        super().__init__(parent)
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 15, 0, 15)
        l.setAlignment(Qt.AlignCenter)
        self.lbl = QLabel(date_text)
        l.addWidget(self.lbl)
        self.lbl.setStyleSheet("color:#94a3b8; font-weight:600; font-size:11px; background:rgba(0,0,0,0.15); border-radius:10px; padding:4px 12px;")

class ChatHeaderButton(QPushButton):
    def __init__(self, icon_char, parent=None):
        super().__init__(icon_char, parent)
        self.setFixedSize(40,40)
        self.setCursor(Qt.PointingHandCursor)
        self.is_dark = True
        self.update_style()

    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self.update_style()

    def update_style(self):
        hover = "rgba(255, 255, 255, 0.1)" if self.is_dark else "rgba(0, 0, 0, 0.05)"
        text_c = "#94a3b8" if self.is_dark else "#64748b"
        self.setStyleSheet(f"QPushButton {{ background:transparent; border:none; font-size:20px; color:{text_c}; border-radius:8px; }} QPushButton:hover {{ background-color:{hover}; }}")

class AttachmentChip(QFrame):
    removed = Signal()

    def __init__(self, path, ftype, parent=None):
        super().__init__(parent)
        self.file_path=path
        self.ftype=ftype
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(path)
        if ftype == 'image':
            self.setFixedSize(80,80)
            self.setStyleSheet("QFrame { background-color: #334155; border-radius: 8px; border: 1px solid #475569; }")
            self.sl=QStackedLayout(self)
            self.sl.setStackingMode(QStackedLayout.StackAll)
            self.sl.setContentsMargins(0,0,0,0)
            self.lp=QLabel()
            self.lp.setAlignment(Qt.AlignCenter)
            self.lp.setStyleSheet("background:transparent; border-radius:8px;")
            self.sl.addWidget(self.lp)
            if path:
                self.l = ChatImageLoader(path)
                self.l.loaded.connect(self.set_img)
                self.l.start()
            bc=QWidget()
            bc.setStyleSheet("background:transparent;")
            cl=QVBoxLayout(bc)
            cl.setContentsMargins(0,4,4,0)
            cl.setAlignment(Qt.AlignTop|Qt.AlignRight)
            cb=QPushButton("✕")
            cb.setFixedSize(20,20)
            cb.setStyleSheet("QPushButton { background-color: #ef4444; color: white; border-radius: 10px; font-weight: bold; border: 1px solid white; }")
            cb.clicked.connect(self.removed.emit)
            cl.addWidget(cb)
            self.sl.addWidget(bc)
        else:
            self.setFixedHeight(32)
            self.setStyleSheet("QFrame { background-color: rgba(99,102,241,0.2); border-radius:16px; border:1px solid rgba(99,102,241,0.4); }")
            l=QHBoxLayout(self)
            l.setContentsMargins(10,0,5,0)
            l.setSpacing(6)
            ic=QLabel("📄")
            ic.setStyleSheet("border:none; background:transparent;")
            nm=path.split('/')[-1]
            ln=QLabel(nm[:9]+"..." if len(nm)>12 else nm)
            ln.setStyleSheet("border:none; background:transparent; color:white; font-weight:500; font-size:12px;")
            cb=QPushButton("✕")
            cb.setFixedSize(18,18)
            cb.setStyleSheet("QPushButton { background-color: rgba(255,255,255,0.2); color:white; border:none; border-radius:9px; }")
            cb.clicked.connect(self.removed.emit)
            l.addWidget(ic)
            l.addWidget(ln)
            l.addWidget(cb)

    def set_img(self, pm):
        if pm and not pm.isNull():
            w,h=80,80
            px=QPixmap.fromImage(pm)
            sc=px.scaled(w,h,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            rn=QPixmap(w,h)
            rn.fill(Qt.transparent)
            p=QPainter(rn)
            p.setRenderHint(QPainter.Antialiasing)
            pt=QPainterPath()
            pt.addRoundedRect(0,0,w,h,8,8)
            p.setClipPath(pt)
            p.drawPixmap(0,0,sc,(sc.width()-w)//2,(sc.height()-h)//2,w,h)
            p.end()
            self.lp.setPixmap(rn)

class AspectRatioLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(False)
        self.original_pixmap=None
        self.loader=None

    def set_full_pixmap(self, img_obj):
        if not img_obj or img_obj.isNull():
            self.setText("Error")
            return
        pm = QPixmap.fromImage(img_obj)
        self.original_pixmap=pm
        sc = pm
        if pm.width()>380 or pm.height()>500:
            sc=pm.scaled(QSize(380,500), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        super().setPixmap(sc)
        self.setFixedSize(sc.size())

class AttachmentPreviewWidget(QFrame):
    attachment_removed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)
        self.setStyleSheet("background:transparent; border:none;")
        self.setVisible(False)
        l=QHBoxLayout(self)
        l.setContentsMargins(20,0,20,0)
        self.sc=QScrollArea()
        self.sc.setWidgetResizable(True)
        self.sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sc.setStyleSheet("background:transparent; border:none;")
        self.cn=QWidget()
        self.cn.setStyleSheet("background:transparent;")
        self.cl=QHBoxLayout(self.cn)
        self.cl.setContentsMargins(0,5,0,5)
        self.cl.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.sc.setWidget(self.cn)
        l.addWidget(self.sc)
        self.atts=[]

    def add_file(self,p,t):
        self.setVisible(True)
        c=AttachmentChip(p,t)
        c.removed.connect(lambda:self.rem(c))
        self.cl.addWidget(c)
        self.atts.append(c)

    def rem(self,c):
        if c in self.atts:
            self.attachment_removed.emit(c.file_path)
            self.atts.remove(c)
            self.cl.removeWidget(c)
            c.deleteLater()
        if not self.atts:
            self.setVisible(False)

    def clear(self):
        for c in self.atts:
            self.cl.removeWidget(c)
            c.deleteLater()
        self.atts=[]
        self.setVisible(False)

class ModernAvatar(QWidget):
    def __init__(self, size=40, text="?", status_color=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(size,size)
        self.tx=text.upper() if text else "?"
        self.pm=None
        self.mv=None
        self.bg=QColor("#6366f1")
        self.st=status_color
        self.ic=ImageCache()
        self.ld=None

    def set_data(self, t, d=None):
        self.tx=t.upper() if t else "?"
        if not d: 
            self.pm=None
            self.mv=None
            self.update()
            return
        if isinstance(d,str) and d.startswith("http"):
            self.ld=ChatImageLoader(d)
            self.ld.loaded.connect(self._ap)
            self.ld.start()
        elif isinstance(d,bytes): self._Lb(d)
        elif isinstance(d,str) and d.startswith("data:"): self._L64(d)
        self.update()

    def _ap(self, io): 
        if io and not io.isNull(): 
            self.pm=QPixmap.fromImage(io)
            self.update()

    def _Lb(self, d):
        if not d: return
        anim = (d[:6].startswith(b'GIF') or b'WEBPVP8' in d[:20])
        k=f"av_{hash(d)&0xFFFFFFFF}"
        if anim: 
            self.bf=QBuffer()
            self.bf.setData(d)
            self.bf.open(QIODevice.ReadOnly)
            self.mv=self.ic.get_movie(k,self.bf)
        if self.mv and self.mv.isValid(): 
            self.mv.frameChanged.connect(self.repaint)
            self.mv.start()
        else: 
            self.pm=self.ic.get_pixmap(k,d)

    def _L64(self, s):
        try: 
            _,e=s.split(',',1)
            self._Lb(base64.b64decode(e))
        except: 
            pass

    def set_status(self,s): 
        self.st=QColor("#4ade80") if s else None
        self.update()

    def paintEvent(self,e):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        pth=QPainterPath()
        pth.addEllipse(0,0,self.width(),self.height())
        p.save()
        p.setClipPath(pth)
        dn=False
        if self.mv and self.mv.state()==QMovie.Running:
            c=self.mv.currentPixmap()
            if not c.isNull(): 
                s=c.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
                p.drawPixmap((self.width()-s.width())//2,(self.height()-s.height())//2,s)
                dn=True
        elif self.pm and not self.pm.isNull():
            s=self.pm.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap((self.width()-s.width())//2,(self.height()-s.height())//2,s)
            dn=True
        if not dn:
            g=QLinearGradient(0,0,self.width(),self.height())
            g.setColorAt(0,self.bg)
            g.setColorAt(1,self.bg.darker(130))
            p.fillRect(self.rect(),g)
            p.setPen(Qt.white)
            p.setFont(QFont("Segoe UI",int(self.height()*0.45),QFont.Bold))
            p.drawText(self.rect(),Qt.AlignCenter,self.tx)
        p.restore()
        if self.st: 
            ds=int(self.width()*0.28)
            p.setPen(QPen(QColor("#181820"),2))
            p.setBrush(self.st)
            p.drawEllipse(QRectF(self.width()-ds-1,self.height()-ds-1,ds,ds))

class SidebarToggle(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30,30)
        self.setCursor(Qt.PointingHandCursor)
        self.c=False

    def paintEvent(self,e):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setBrush(QColor(255,255,255,30))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(self.rect(),6,6)
        p.translate(self.width()/2,self.height()/2)
        if self.c: p.rotate(180)
        p.setPen(QPen(QColor(200,200,200),2))
        pt=QPainterPath()
        pt.moveTo(3,-5)
        pt.lineTo(-3,0)
        pt.lineTo(3,5)
        p.drawPath(pt)

    def set_collapsed(self, s):
        self.c=s
        self.update()

class RichLoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60,60)
        self.angle=0
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.is_spin=False

    def rotate(self):
        self.angle=(self.angle+10)%360
        self.update()

    def start(self):
        if not self.is_spin:
            self.timer.start(30)
            self.is_spin=True
            self.setVisible(True)

    def stop(self):
        self.timer.stop()
        self.is_spin=False
        self.setVisible(False)

    def paintEvent(self, e):
        if not self.is_spin: return
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        p.translate(w/2,h/2)
        p.rotate(self.angle)
        g=QConicalGradient(0,0,0)
        g.setColorAt(0,QColor("#6366f1"))
        g.setColorAt(0.8,Qt.transparent)
        p.setPen(QPen(QBrush(g),5,Qt.SolidLine,Qt.RoundCap))
        p.drawArc(int((10-w)/2),int((10-h)/2),w-10,h-10,0,360*16)

class ActionMorphButton(QAbstractButton):
    def __init__(self, mode='attach', parent=None):
        super().__init__(parent)
        self.setFixedSize(40,40)
        self.setCursor(Qt.PointingHandCursor)
        self.mode=mode
        self._m=0.0
        self._s=0.0
        self.is_dark=True
        self.am=QPropertyAnimation(self,b"morph",self)
        self.am.setDuration(300)
        self.asend=QPropertyAnimation(self,b"snd",self)
        self.asend.setDuration(400)
        self.asend.finished.connect(lambda:self.set_snd(0.0))

    def get_m(self): return self._m
    def set_m(self,v): self._m=v; self.update()
    morph=Property(float,get_m,set_m)

    def get_snd(self): return self._s
    def set_snd(self,v): self._s=v; self.update()
    snd=Property(float,get_snd,set_snd)

    def enterEvent(self,e): 
        self.am.setEndValue(1.0)
        self.am.start()
        super().enterEvent(e)

    def leaveEvent(self,e): 
        self.am.setEndValue(0.0)
        self.am.start()
        super().leaveEvent(e)

    def animate_send(self):
        if self.mode=='send': 
            self.asend.stop()
            self.asend.setStartValue(0.0)
            self.asend.setEndValue(1.0)
            self.asend.start()

    def set_theme(self, d): 
        self.is_dark=d
        self.update()

    def paintEvent(self,e):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c=self.rect().center()
        ic = QColor(180,180,180) if self.is_dark else QColor(100,100,100)
        ac = QColor("#6366f1") if self.is_dark else QColor("white")
        if self._m>0:
            p.setBrush(QColor(255,255,255,30))
            p.setPen(Qt.NoPen)
            s=36*(0.8+0.2*self._m)
            p.drawEllipse(c,s/2,s/2)
        r,g,b=ic.red(),ic.green(),ic.blue()
        ar,ag,ab=ac.red(),ac.green(),ac.blue()
        cur=QColor(int(r+(ar-r)*self._m),int(g+(ag-g)*self._m),int(b+(ab-b)*self._m))
        p.setPen(QPen(cur,2.2))
        p.setBrush(Qt.NoBrush)
        if self.mode=='attach':
            t=self._m
            p.save()
            p.translate(c)
            if t<1:
                p.save()
                p.scale(1-0.5*t,1-0.5*t)
                p.rotate(90*t)
                p.drawLine(0,-6,0,6)
                p.drawLine(-6,0,6,0)
                p.restore()
            if t>0:
                p.save()
                p.setOpacity(t)
                p.scale(0.5+0.5*t,0.5+0.5*t)
                pt=QPainterPath()
                pt.moveTo(2,-4)
                pt.lineTo(2,3)
                pt.arcTo(-4,0,6,6,0,-180)
                pt.lineTo(-4,-4)
                pt.arcTo(-4,-7,4,4,180,-180)
                pt.lineTo(0,2)
                p.drawPath(pt)
                p.restore()
            p.restore()
        elif self.mode=='emoji':
            p.translate(c)
            s=1+0.1*self._m
            p.scale(s,s)
            p.drawEllipse(QPoint(0,0),9,9)
            p.drawEllipse(QPoint(-3,-2),1,1)
            p.drawEllipse(QPoint(3,-2),1,1)
            pa=QPainterPath()
            pa.arcMoveTo(QRectF(-5,-5,10,10),225)
            pa.arcTo(QRectF(-5,-5,10,10),225,90)
            p.drawPath(pa)
        elif self.mode=='send':
            f=self._s
            p.translate(c)
            if f>0: 
                p.translate(30*f,-30*f)
                p.setOpacity(1-f)
            pa=QPainterPath()
            pa.moveTo(-4,-3)
            pa.lineTo(5,1)
            pa.lineTo(-4,5)
            pa.lineTo(-2,1)
            pa.lineTo(-4,-3)
            p.translate(-1,-1)
            p.drawPath(pa)

class ChatListItem(QWidget):
    context_action = Signal(str, dict)

    def __init__(self, data, is_collapsed=False):
        super().__init__()
        self.data = data
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12,10,12,10)
        self.layout.setSpacing(12)
        self.setStyleSheet("background:transparent;")
        u = data.get('username',"U")
        d = data.get('display_name') or u
        av_url = data.get('avatar_url')
        self.avatar = ModernAvatar(48, d[0])
        self.avatar.set_data(d[0], av_url)
        self.layout.addWidget(self.avatar)
        self.info_widget = QWidget()
        self.info_layout = QVBoxLayout(self.info_widget)
        self.info_layout.setContentsMargins(0,0,0,0)
        self.info_layout.setSpacing(4)
        top = QHBoxLayout()
        self.name_lbl = QLabel(d)
        self.name_lbl.setStyleSheet("font-weight:700; color:white; font-size:15px; border:none; background:transparent;")
        top.addWidget(self.name_lbl)
        top.addStretch()
        self.date_lbl = QLabel("")
        ts = data.get('timestamp')
        if ts:
            try: 
                dt = date_parser.parse(ts)
                self.date_lbl.setText(dt.strftime("%d.%m.%Y"))
            except: 
                pass
        self.date_lbl.setStyleSheet("color:#94a3b8; font-size:11px; background:transparent; border:none;")
        top.addWidget(self.date_lbl)
        msg = str(data.get('last_message') or "Нет сообщений")
        if ATTACHMENT_SPLITTER in msg:
            p = msg.split(ATTACHMENT_SPLITTER)
            t = p[0].strip()
            if t: 
                msg = t
            elif any('cmd://image' in x for x in p): 
                msg = "🖼️ Изображение"
            elif any('cmd://file' in x for x in p): 
                msg = "📄 Документ"
            else: 
                msg = "Вложение"
        elif "cmd://image" in msg: 
            msg = "🖼️ Изображение"
        elif "cmd://file" in msg: 
            msg = "📄 Документ"
        elided = QFontMetrics(QFont("Segoe UI", 13)).elidedText(msg.replace('\n',' '), Qt.ElideRight, 180)
        self.m_lbl = QLabel(elided)
        self.m_lbl.setStyleSheet("color:#94a3b8; font-size:13px; background:transparent; border:none;")
        self.info_layout.addLayout(top)
        self.info_layout.addWidget(self.m_lbl)
        self.layout.addWidget(self.info_widget)
        self.set_collapsed(is_collapsed)

    def show_context_menu(self, pos):
        m = QMenu(self)
        is_dark = "white" in self.name_lbl.styleSheet()
        bg = "#2b2b36" if is_dark else "white"
        fg = "white" if is_dark else "black"
        bd = "#444" if is_dark else "#e5e7eb"
        m.setStyleSheet(f"QMenu {{ background-color: {bg}; color: {fg}; border: 1px solid {bd}; border-radius: 8px; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: #6366f1; color: white; }}")
        m.addAction("📌 Закрепить", lambda: self.context_action.emit("pin", self.data))
        m.addAction("🗑 Очистить", lambda: self.context_action.emit("clear_history", self.data))
        m.exec(self.mapToGlobal(pos))

    def set_theme(self, is_dark): 
        c = "white" if is_dark else "#1f2937"
        self.name_lbl.setStyleSheet(f"font-weight:700; color:{c}; font-size:15px; background:transparent; border:none;")
        self.m_lbl.setStyleSheet("color:#94a3b8; font-size:13px; background:transparent; border:none;")
        self.date_lbl.setStyleSheet("color:#94a3b8; font-size:11px; background:transparent; border:none;")

    def set_collapsed(self, c):
        self.info_widget.setVisible(not c)
        if c: 
            self.layout.setContentsMargins(0,10,0,10)
            self.layout.setAlignment(Qt.AlignCenter)
        else: 
            self.layout.setContentsMargins(15,10,15,10)
            self.layout.setAlignment(Qt.AlignLeft)

class ChatBubble(QFrame):
    def __init__(self, text, is_own, attachments=None, timestamp=None, is_read=False):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setMinimumWidth(80)
        self.setMaximumWidth(600)
        self.is_own=is_own
        self.attachments = attachments or []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12,10,12,8)
        self.layout.setSpacing(6)
        if text: 
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse|Qt.LinksAccessibleByMouse)
            lbl.setOpenExternalLinks(True)
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            lbl.setMaximumWidth(580)
            lbl.setFont(QFont("Segoe UI", 10))
            self.lbl_text = lbl
            self.layout.addWidget(lbl)
        else: 
            self.lbl_text = None
        for a in self.attachments:
            url = a.get('url')
            if a.get('type') == 'image':
                al = AspectRatioLabel()
                al.setStyleSheet("background:rgba(0,0,0,0.1); border-radius:8px;")
                al.setCursor(Qt.PointingHandCursor)
                ld = ChatImageLoader(url)
                ld.loaded.connect(lambda p, w=al: w.set_full_pixmap(p))
                ld.start()
                al.mousePressEvent = lambda e, u=url: self._open_viewer(u)
                self.layout.addWidget(al)
            else:
                f = QFrame()
                f.setStyleSheet("background:rgba(0,0,0,0.15); border-radius:6px;")
                f.setFixedHeight(40)
                f.setCursor(Qt.PointingHandCursor)
                fl = QHBoxLayout(f)
                fl.setContentsMargins(10,0,10,0)
                fl.addWidget(QLabel("📄", styleSheet="background:transparent; border:none;"))
                fl.addWidget(QLabel(str(url).split('/')[-1], styleSheet="color:inherit; background:transparent; border:none; font-weight:bold;"))
                f.mousePressEvent = lambda e, u=url: open_local_or_remote_file(u)
                self.layout.addWidget(f)
        meta = QHBoxLayout()
        meta.addStretch()
        t = timestamp.strftime("%H:%M") if timestamp else ""
        self.t_lbl = QLabel(t)
        meta.addWidget(self.t_lbl)
        if is_own: 
            self.s_lbl = QLabel("✓✓" if is_read else "✓")
            meta.addWidget(self.s_lbl)
        else: 
            self.s_lbl = None
        self.layout.addLayout(meta)
        self.update_bubble_theme(True)

    def _open_viewer(self, u):
        l = ChatImageLoader(u)
        l.loaded.connect(lambda p: HybridGalleryOverlay(QPixmap.fromImage(p), self.window()).exec() if p else None)
        self._tmp = l
        l.start()

    def update_bubble_theme(self, is_dark):
        own = self.is_own
        if own: 
            bg="#6366f1"
            tc="white"
            mc="rgba(255,255,255,0.7)"
            r="border-radius:14px; border-bottom-right-radius:2px;"
            sc="#99f6e4"
        else:
            if is_dark: 
                bg,tc,mc = "#252530","#e2e8f0","#94a3b8"
            else: 
                bg,tc,mc = "#ffffff","#1f2937","#6b7280"
            r="border-radius:14px; border-bottom-left-radius:2px;"
            sc=""
        self.setStyleSheet(f"QFrame {{ background-color:{bg}; {r} }} QLabel {{ border:none; background:transparent; }}")
        if self.lbl_text: 
            self.lbl_text.setStyleSheet(f"color: {tc}; border:none; background:transparent;")
        self.t_lbl.setStyleSheet(f"font-size:10px; color:{mc}; background:transparent;")
        if self.s_lbl: 
            self.s_lbl.setStyleSheet(f"font-size:10px; font-weight:bold; margin-left:4px; color:{sc}; background:transparent;")

class MessageRow(QWidget):
    action_delete = Signal()
    action_edit = Signal()

    def __init__(self, content, is_own, sender_name, avatar_url, attachments=None, timestamp=None, is_read=False, parent=None, is_first_in_chat=False):
        super().__init__(parent)
        self.is_own = is_own
        self._is_dark = True
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.ctx)
        l = QHBoxLayout(self)
        l.setContentsMargins(10,2,10,2)
        l.setSpacing(8)
        self.av = ModernAvatar(34, sender_name[0] if sender_name else "?")
        self.av.set_data(sender_name[0], avatar_url)
        self.bub = ChatBubble(content, is_own, attachments, timestamp, is_read)
        if is_own:
            l.addStretch()
            l.addWidget(self.bub, 0, Qt.AlignTop)
        else:
            l.addWidget(self.av, 0, Qt.AlignBottom)
            l.addWidget(self.bub, 0, Qt.AlignTop)
            l.addStretch()

    def ctx(self, p):
        m = QMenu(self)
        bg = "#2b2b36" if self._is_dark else "white"
        fg = "white" if self._is_dark else "black"
        bd = "#444" if self._is_dark else "#cbd5e1"
        m.setStyleSheet(f"QMenu {{ background-color: {bg}; color: {fg}; border: 1px solid {bd}; border-radius: 6px; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: #6366f1; color: white; }}")
        m.addAction("Копировать", self._copy_text)
        m.addAction("Всё скопировать", self._copy_all)
        m.addSeparator()
        if self.is_own:
            m.addAction("✏ Изменить", self.action_edit.emit)
            m.addAction("🗑 Удалить", self.action_delete.emit)
        m.exec(self.mapToGlobal(p))

    def _copy_text(self):
        if self.bub.lbl_text:
            QApplication.clipboard().setText(self.bub.lbl_text.text())

    def _copy_all(self):
        t = self.bub.lbl_text.text() if self.bub.lbl_text else ""
        tm = self.bub.t_lbl.text()
        QApplication.clipboard().setText(f"[{tm}] {t}")

    def set_theme(self, d): 
        self._is_dark = d
        self.bub.update_bubble_theme(d)

class MessageTextEdit(QTextEdit):
    submit_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(100)
        self.setMinimumHeight(40)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            if e.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(e)
                self.adjust_height()
            else:
                self.submit_pressed.emit()
                e.accept()
        else:
            super().keyPressEvent(e)

    def adjust_height(self):
        h = self.document().size().height()
        self.setMinimumHeight(min(100, max(40, int(h)+10)))