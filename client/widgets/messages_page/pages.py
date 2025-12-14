import datetime
import time
import threading
import requests
from dateutil import parser as date_parser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QListWidget, QListWidgetItem,
    QLineEdit, QMenu, QMessageBox, QFileDialog,
    QStackedWidget, QInputDialog, QApplication
)
from PySide6.QtCore import Qt, QSize, QTimer, QPoint, Slot, QThreadPool
from PySide6.QtGui import QAction, QPalette, QColor
from . import network
from .network import (
    ThreadPoolManager, fetch_avatar_data, fetch_full_profile,
    fetch_chat_data, task_batch_send, HeaderResultSignaler,
    ChatLoader, HistoryLoader, ATTACHMENT_SPLITTER
)
from .widgets import (
    ModernAvatar, SidebarToggle, RichLoadingSpinner, ActionMorphButton,
    ChatListItem, MessageRow, MessageTextEdit, AttachmentPreviewWidget,
    ChatHeaderButton, MAX_ATTACHMENTS, DateHeaderWidget
)
from client.widgets.profile_page import ProfileViewDialog
from .dialogs import EmojiPicker

class MessagesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user = None
        self.active_chat_user = None
        self.my_avatar_data = None
        self.is_dark = True
        self.pending_attachments = []
        self._last_emoji_close_time = 0
        self.messages_list_data = []
        self.loaded_count = 0
        self.is_loading_history = False
        self.is_list_collapsed = False
        self.last_typing_sent = 0.0
        self.pinned_chats = set()
        
        self.chat_list_timer = QTimer(self)
        self.chat_list_timer.timeout.connect(self.refresh_chat_list_safe)
        
        self.msg_poll_timer = QTimer(self)
        self.msg_poll_timer.timeout.connect(self.poll_new_messages)
        
        self.typing_poll_timer = QTimer(self)
        self.typing_poll_timer.timeout.connect(self.check_typing_status)
        
        self.typing_hide_timer = QTimer(self)
        self.typing_hide_timer.setSingleShot(True)
        self.typing_hide_timer.timeout.connect(self.hide_typing_label)

        self.header_signaler = HeaderResultSignaler()
        self.header_signaler.updated.connect(self._update_header_ui)
        
        self.setup_ui()
        self.setup_attach_menu()
        self.setup_emoji_menu()

    def showEvent(self, event):
        pal = QApplication.palette()
        self.is_dark = (pal.color(QPalette.Window).lightness() < 128)
        self.apply_theme()
        super().showEvent(event)

    def start_worker(self, worker):
        QThreadPool.globalInstance().start(worker)

    def set_current_user(self, u):
        self.current_user = u
        self.list_w.clear()
        self.active_chat_user = None
        self.clear_chat_area()
        self.welcome_screen_mode(True)
        
        if self.current_user:
            self._fetch_my_avatar_data()
            self.refresh_chat_list_safe()
            self.chat_list_timer.start(5000)
        else:
            self.chat_list_timer.stop()
            self.msg_poll_timer.stop()
            self.typing_poll_timer.stop()

    def apply_theme(self):
        d = self.is_dark
        l_bg = "#121217" if d else "#ffffff"
        l_br = "#252530" if d else "#f3f4f6"
        s_bg = "#202028" if d else "#f9fafb"
        s_br = "#2d2d3b" if d else "#e5e7eb"
        tit_c = "white" if d else "#111827"
        
        self.left_panel.setStyleSheet(f"QWidget#LeftPanelContainer {{ background-color: {l_bg}; border-right: 1px solid {l_br}; }}")
        self.dialogs_title.setStyleSheet(f"font-size:24px; font-weight:800; color:{tit_c}; border:none; font-family:'Segoe UI';")
        self.search_inp.setStyleSheet(f"QLineEdit {{ background-color: {s_bg}; border: 1px solid {s_br}; border-radius: 8px; padding: 8px 12px; color: {'white' if d else 'black'}; }}")
        self.list_w.setStyleSheet("QListWidget { background: transparent; border: none; } QListWidget::item:hover { background-color: rgba(127,127,127,0.1); } QListWidget::item:selected { background-color: rgba(99, 102, 241, 0.2); }")

        r_bg = "#121217" if d else "#ffffff"
        h_bg = "#1e1e2d" if d else "#ffffff"
        inp_c = "white" if d else "#1f2937"
        self.right_panel.setStyleSheet(f"QWidget {{ background-color: {r_bg}; }}")
        self.chead.setStyleSheet(f"QFrame {{ background-color: {h_bg}; border-bottom: 1px solid {l_br}; }}")
        self.head_name.setStyleSheet(f"font-size:16px; font-weight:bold; color:{'white' if d else 'black'}; border:none; background:transparent;")
        self.pill_frame.setStyleSheet(f"QFrame {{ background-color: {h_bg}; border-top: 1px solid {l_br}; }}")
        self.inp.setStyleSheet(f"QTextEdit {{ border: none; background: transparent; color: {inp_c}; font-size: 16px; }}")
        
        self.btn_att.set_theme(d)
        self.btn_send.set_theme(d)
        self.btn_emoji.set_theme(d)
        self.btn_options.set_theme(d)
        for i in range(self.list_w.count()):
            w = self.list_w.itemWidget(self.list_w.item(i))
            if isinstance(w, ChatListItem):
                w.set_theme(d)
        
        self._refresh_messages_visual_theme()

    def _refresh_messages_visual_theme(self):
        for i in range(self.alay.count()):
            item = self.alay.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if hasattr(w, 'set_theme'):
                    w.set_theme(self.is_dark)

    def _fetch_my_avatar_data(self):
        threading.Thread(target=lambda: setattr(self, 'my_avatar_data', fetch_avatar_data(self.current_user))).start()

    def setup_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.left_panel = QWidget()
        self.left_panel.setObjectName("LeftPanelContainer")
        self.left_panel.setFixedWidth(320)
        lv = QVBoxLayout(self.left_panel)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        h_fr = QFrame()
        h_fr.setFixedHeight(70)
        h_fr.setStyleSheet("background:transparent; border:none;")
        hl = QHBoxLayout(h_fr)
        hl.setContentsMargins(20, 0, 15, 0)
        self.dialogs_title = QLabel("Диалоги")
        self.btn_toggle = SidebarToggle()
        self.btn_toggle.clicked.connect(self.toggle_chat_list)
        hl.addWidget(self.dialogs_title)
        hl.addStretch()
        hl.addWidget(self.btn_toggle)
        lv.addWidget(h_fr)
        sc = QWidget()
        sc.setStyleSheet("background:transparent;")
        sl = QVBoxLayout(sc)
        sl.setContentsMargins(15, 0, 15, 10)
        self.search_inp = QLineEdit()
        self.search_inp.setPlaceholderText("Поиск...")
        self.search_inp.textChanged.connect(self._filter_chat_list)
        sl.addWidget(self.search_inp)
        self.search_container = sc
        lv.addWidget(sc)
        self.list_w = QListWidget()
        self.list_w.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list_w.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_w.setFrameShape(QFrame.NoFrame)
        self.list_w.itemClicked.connect(self.on_chat_selected)
        lv.addWidget(self.list_w)
        
        self.right_panel = QWidget()
        rv = QVBoxLayout(self.right_panel)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        self.chead = QFrame()
        self.chead.setFixedHeight(70)
        chl = QHBoxLayout(self.chead)
        chl.setContentsMargins(20, 0, 20, 0)
        chl.setSpacing(12)
        self.head_avatar = ModernAvatar(42, "?")
        self.head_name = QLabel("")
        self.head_status = QLabel("")
        htl = QVBoxLayout()
        htl.setSpacing(2)
        htl.setAlignment(Qt.AlignVCenter)
        htl.addWidget(self.head_name)
        htl.addWidget(self.head_status)
        self.typing_label = QLabel("Печатает...")
        self.typing_label.setStyleSheet("color:#6366f1; font-style:italic; font-size:12px; background:transparent;")
        self.typing_label.setVisible(False)
        self.btn_options = ChatHeaderButton("⋮")
        self.btn_options.clicked.connect(self.show_header_menu)
        chl.addWidget(self.head_avatar)
        chl.addLayout(htl)
        chl.addWidget(self.typing_label)
        chl.addStretch()
        chl.addWidget(self.btn_options)
        rv.addWidget(self.chead)
        
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background:transparent;")
        self.scroll_page = QWidget()
        spl = QVBoxLayout(self.scroll_page)
        spl.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none; background:transparent;} QScrollBar:vertical{width:8px; background:transparent;} QScrollBar::handle:vertical{background:#475569; border-radius:4px; min-height:20px;}")
        self.scroll.verticalScrollBar().valueChanged.connect(self.check_pagination)
        self.area_w = QWidget()
        self.area_w.setStyleSheet("background:transparent;")
        self.alay = QVBoxLayout(self.area_w)
        self.alay.setContentsMargins(20, 20, 20, 20)
        self.alay.setSpacing(10)
        self.alay.addStretch()
        self.scroll.setWidget(self.area_w)
        spl.addWidget(self.scroll)
        self.loading_page = QWidget()
        lpl = QVBoxLayout(self.loading_page)
        lpl.setAlignment(Qt.AlignCenter)
        self.spinner = RichLoadingSpinner(self.loading_page)
        lpl.addWidget(self.spinner)
        self.content_stack.addWidget(self.scroll_page)
        self.content_stack.addWidget(self.loading_page)
        rv.addWidget(self.content_stack)
        
        self.attachment_preview = AttachmentPreviewWidget()
        self.attachment_preview.attachment_removed.connect(self.remove_attachment_data)
        rv.addWidget(self.attachment_preview)
        self.pill_frame = QFrame()
        self.pill_frame.setFixedHeight(70)
        il = QHBoxLayout(self.pill_frame)
        il.setContentsMargins(20, 10, 20, 10)
        il.setSpacing(10)
        self.btn_att = ActionMorphButton('attach')
        self.inp = MessageTextEdit()
        self.inp.setPlaceholderText("Напишите сообщение...")
        self.inp.textChanged.connect(self.inp.adjust_height)
        self.inp.textChanged.connect(self.on_input_text_changed)
        self.inp.submit_pressed.connect(self.send_text)
        self.btn_emoji = ActionMorphButton('emoji')
        self.btn_send = ActionMorphButton('send')
        self.btn_send.clicked.connect(self.send_text)
        il.addWidget(self.btn_att)
        il.addWidget(self.inp, 1)
        il.addWidget(self.btn_emoji)
        il.addWidget(self.btn_send)
        rv.addWidget(self.pill_frame)
        
        self.welcome_widget = QLabel("Выберите чат\nили начните новый диалог")
        self.welcome_widget.setAlignment(Qt.AlignCenter)
        main.addWidget(self.left_panel)
        main.addWidget(self.right_panel)
        main.addWidget(self.welcome_widget)
        self.welcome_screen_mode(True)

    def on_input_text_changed(self):
        if time.time() - self.last_typing_sent > 3.0:
            self.last_typing_sent = time.time()
            threading.Thread(target=self._send_typing_status, args=(True,), daemon=True).start()

    def _send_typing_status(self, s):
        if self.active_chat_user:
            try:
                requests.post(f"{network.API_URL}/messages/typing", json={"user": self.current_user, "target": self.active_chat_user, "status": s}, verify=False)
            except:
                pass

    def check_typing_status(self):
        threading.Thread(target=self._worker_check_typing, daemon=True).start()

    def _worker_check_typing(self):
        try:
            r = requests.get(f"{network.API_URL}/messages/typing", params={"user": self.active_chat_user, "me": self.current_user}, verify=False, timeout=2)
            if r.json().get("is_typing"):
                QTimer.singleShot(0, self.show_typing_label)
        except:
            pass

    def show_typing_label(self):
        self.typing_label.setVisible(True)
        self.typing_hide_timer.start(4000)

    def hide_typing_label(self):
        self.typing_label.setVisible(False)

    def show_header_menu(self):
        if not self.active_chat_user:
            return
        menu = QMenu(self)
        bg = "#2b2b36" if self.is_dark else "white"
        fg = "white" if self.is_dark else "black"
        bd = "#444" if self.is_dark else "#e5e7eb"
        sel = "#6366f1"
        menu.setStyleSheet(f"QMenu {{ background-color: {bg}; color: {fg}; border: 1px solid {bd}; border-radius: 8px; }} QMenu::item {{ padding: 8px 24px; border-radius: 4px; }} QMenu::item:selected {{ background-color: {sel}; color: white; }}")
        menu.addAction("👤 Показать профиль", lambda: ProfileViewDialog(self.active_chat_user, self.window()).exec())
        menu.addAction("🗑 Очистить переписку", lambda: self.handle_list_action("clear_history", {'username': self.active_chat_user}))
        menu.addAction("☠ Удалить чат", lambda: self.handle_list_action("delete_chat", {'username': self.active_chat_user}))
        menu.exec(self.btn_options.mapToGlobal(QPoint(0, self.btn_options.height())))

    def toggle_chat_list(self):
        if self.is_list_collapsed:
            self.expand_list()
        else:
            self.collapse_list()

    def collapse_list(self):
        self.is_list_collapsed = True
        self.left_panel.setFixedWidth(80)
        self.dialogs_title.hide()
        self.search_container.hide()
        self.btn_toggle.set_collapsed(True)
        self.update_list_items_mode()

    def expand_list(self):
        self.is_list_collapsed = False
        self.left_panel.setFixedWidth(320)
        self.dialogs_title.show()
        self.search_container.show()
        self.btn_toggle.set_collapsed(False)
        self.update_list_items_mode()
        self.search_inp.setFocus()

    def update_list_items_mode(self):
        for i in range(self.list_w.count()):
            w = self.list_w.itemWidget(self.list_w.item(i))
            if w:
                w.set_collapsed(self.is_list_collapsed)

    def _filter_chat_list(self, t):
        st = t.lower().strip()
        for i in range(self.list_w.count()):
            it = self.list_w.item(i)
            w = self.list_w.itemWidget(it)
            if w:
                it.setHidden(st not in w.data.get('username','').lower())

    def setup_attach_menu(self):
        self.attach_menu = QMenu(self)
        self.attach_menu.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        ad = QAction("📄 Документ", self)
        ad.triggered.connect(self.attach_document)
        ai = QAction("🖼️ Изображение", self)
        ai.triggered.connect(self.attach_image)
        self.attach_menu.addAction(ad)
        self.attach_menu.addAction(ai)
        self.btn_att.clicked.connect(self.show_attach_menu)

    def show_attach_menu(self):
        bg = "#2b2b36" if self.is_dark else "white"
        fg = "white" if self.is_dark else "black"
        bd = "#444" if self.is_dark else "#e5e7eb"
        self.attach_menu.setStyleSheet(f"QMenu {{ background-color:{bg}; color:{fg}; border:1px solid {bd}; border-radius:6px; }} QMenu::item:selected {{ background:#6366f1; color:white; }}")
        p = self.btn_att.mapToGlobal(QPoint(0, 0))
        y = p.y() - self.attach_menu.sizeHint().height() - 8
        self.attach_menu.exec(QPoint(p.x(), y))

    def setup_emoji_menu(self):
        self.emoji_picker = EmojiPicker(self)
        self.emoji_picker.emoji_selected.connect(self.insert_emoji)
        self.btn_emoji.clicked.connect(self.show_emoji_picker)

    def show_emoji_picker(self):
        if time.time() - self._last_emoji_close_time < 0.3:
            return
        p = self.btn_emoji.mapToGlobal(QPoint(0, 0))
        x = (p.x()+self.btn_emoji.width()) - self.emoji_picker.width()
        y = p.y() - self.emoji_picker.height() - 10
        self.emoji_picker.move(max(10, x), y)
        self.emoji_picker.show()
        self.emoji_picker.raise_()

    def insert_emoji(self, e):
        self.inp.insertPlainText(e)
        self.inp.setFocus()

    def attach_document(self):
        if self.active_chat_user:
            fs, _ = QFileDialog.getOpenFileNames(self, "Files", "", "All (*.*)")
            for p in fs:
                self.add_attachment(p,'file')

    def attach_image(self):
        if self.active_chat_user:
            fs, _ = QFileDialog.getOpenFileNames(self, "Images", "", "Image (*.png *.jpg *.gif)")
            for p in fs:
                self.add_attachment(p,'image')

    def add_attachment(self, p, t):
        self.pending_attachments.append({'path':p,'type':t})
        self.attachment_preview.add_file(p,t)

    def remove_attachment_data(self, p):
        self.pending_attachments=[a for a in self.pending_attachments if a['path']!=p]

    def clear_attachment_full(self):
        self.pending_attachments = []
        self.attachment_preview.clear()

    def welcome_screen_mode(self, w):
        self.right_panel.setVisible(not w)
        self.welcome_widget.setVisible(w)

    def refresh_chat_list_safe(self):
        if not self.current_user:
            return
        loader = ChatLoader(self.current_user)
        loader.signals.loaded.connect(self._fill_chats)
        self.start_worker(loader)

    def _fill_chats(self, chats):
        if not chats:
            return
        existing = {}
        for i in range(self.list_w.count()):
            it = self.list_w.item(i)
            d = it.data(Qt.UserRole)
            if d and 'username' in d:
                existing[d['username']] = it
        
        pinned, normal = [], []
        for c in chats:
            if c['username'] in self.pinned_chats:
                pinned.append(c)
            else:
                normal.append(c)
        
        curs = set()
        for c in pinned + normal:
            u = c['username']
            curs.add(u)
            if u in existing:
                it = existing[u]
                w = self.list_w.itemWidget(it)
                if isinstance(w, ChatListItem):
                    if w.data.get('last_message') != c.get('last_message') or w.data.get('timestamp') != c.get('timestamp') or w.data.get('avatar_url') != c.get('avatar_url'):
                        nw = ChatListItem(c, self.is_list_collapsed)
                        nw.set_theme(self.is_dark)
                        nw.context_action.connect(self.handle_list_action)
                        self.list_w.setItemWidget(it, nw)
                        it.setData(Qt.UserRole, c)
            else:
                it = QListWidgetItem()
                it.setSizeHint(QSize(0, 72))
                it.setData(Qt.UserRole, c)
                w = ChatListItem(c, self.is_list_collapsed)
                w.set_theme(self.is_dark)
                w.context_action.connect(self.handle_list_action)
                self.list_w.addItem(it)
                self.list_w.setItemWidget(it, w)
        for i in range(self.list_w.count() - 1, -1, -1):
            if self.list_w.item(i).data(Qt.UserRole)['username'] not in curs:
                self.list_w.takeItem(i)

    def _update_list_preview(self, u_target, text, ts):
        for i in range(self.list_w.count()):
            it = self.list_w.item(i)
            d = it.data(Qt.UserRole)
            if d['username'] == u_target:
                d['last_message'] = text
                d['timestamp'] = ts
                nw = ChatListItem(d, self.is_list_collapsed)
                nw.set_theme(self.is_dark)
                nw.context_action.connect(self.handle_list_action)
                self.list_w.setItemWidget(it, nw)
                it.setData(Qt.UserRole, d)
                return

    def on_chat_selected(self, item):
        self.open_new_chat(item.data(Qt.UserRole).get('username'), item.data(Qt.UserRole))

    def handle_list_action(self, act, data):
        u = data.get('username')
        if not u:
            return
        if act=="pin":
            if u in self.pinned_chats:
                self.pinned_chats.remove(u)
            else:
                self.pinned_chats.add(u)
            self.refresh_chat_list_safe()
        elif act=="clear_history":
            requests.post(f"{network.API_URL}/messages/clear", json={"me":self.current_user,"target":u,"for_all":False},verify=False)
            self.open_new_chat(u)

    def open_new_chat(self, partner, full=None):
        self.msg_poll_timer.stop()
        self.welcome_screen_mode(False)
        
        self.active_chat_user = partner
        self.loaded_count = 0
        self.messages_list_data = []
        self.clear_chat_area()
        self.clear_attachment_full()
        
        self._apply_header_data(full if full else {"username":partner})
        self.spinner.start()
        self.content_stack.setCurrentIndex(1)
        threading.Thread(target=self._bg_fetch_header, args=(partner,), daemon=True).start()
        QTimer.singleShot(100, self._load_initial_history)
        self.typing_poll_timer.start(2500)

    def _bg_fetch_header(self, u):
        self.header_signaler.updated.emit(fetch_full_profile(u) or {"username":u})

    def _update_header_ui(self, d):
        if d.get('username') == self.active_chat_user:
            self._apply_header_data(d)

    def _apply_header_data(self, d):
        dn = d.get('display_name') or d.get('username', "Unknown")
        self.head_name.setText(dn)
        io = d.get('is_online', False)
        self.head_status.setText("В сети" if io else "Не в сети")
        self.head_status.setStyleSheet(f"color:{'#4ade80' if io else '#94a3b8'}; background:transparent; border:none;")
        self.head_avatar.set_data((d.get('display_name') or "U")[0], d.get('avatar_url'))
        self.head_avatar.set_status(io)

    def _load_initial_history(self):
        self.is_loading_history = True
        loader = HistoryLoader(self.current_user, self.active_chat_user, 0, 50)
        loader.signals.result_ready.connect(self._handle_history_loaded)
        self.start_worker(loader)
        QTimer.singleShot(8000, self._force_stop_loading)

    def _force_stop_loading(self):
        if self.is_loading_history and self.content_stack.currentIndex()==1:
            self.spinner.stop()
            self.content_stack.setCurrentIndex(0)
            self.is_loading_history=False
            self.msg_poll_timer.start(3000)

    def check_pagination(self, v):
        if v < 50 and not self.is_loading_history and self.loaded_count >= 50:
            self.is_loading_history = True
            w = HistoryLoader(self.current_user, self.active_chat_user, self.loaded_count, 30)
            w.signals.result_ready.connect(self._handle_history_loaded)
            self.start_worker(w)

    def _handle_history_loaded(self, msgs, off):
        self.content_stack.setCurrentIndex(0)
        self.is_loading_history=False
        if not msgs and off==0:
            self.msg_poll_timer.start(3000)
            return
        if off == 0:
            self.messages_list_data = msgs
            self.redraw_chat(True)
            QTimer.singleShot(50, self.scroll_to_bottom)
        else:
            old_h = self.scroll.verticalScrollBar().maximum()
            self.messages_list_data = msgs + self.messages_list_data
            self.redraw_chat(True)
            QTimer.singleShot(10, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()-old_h))
        self.loaded_count = len(self.messages_list_data)
        if off==0:
            self.msg_poll_timer.start(3000)

    def redraw_chat(self, full=False):
        if full:
            self.clear_chat_area()
            ld = None
            for m in self.messages_list_data:
                try:
                    if m.get('created_at'):
                        ds = date_parser.parse(m['created_at']).strftime("%Y-%m-%d")
                        if ds != ld:
                            self.alay.insertWidget(self.alay.count()-1, DateHeaderWidget(ds, parent=self))
                            ld = ds
                except:
                    pass
                self._add_bubble_to_ui(m, -1)

    def _add_bubble_to_ui(self, m, index=-1):
        txt, atts = self._parse_message_content(m)
        ts = datetime.datetime.now()
        try:
            if m.get('created_at'):
                ts = date_parser.parse(m['created_at'])
        except:
            pass
        r = MessageRow(txt, m.get('sender_name')==self.current_user, m.get('sender_name'), m.get('avatar_url'), atts, ts, m.get('is_read'))
        r.set_theme(self.is_dark)
        r.action_delete.connect(lambda: self.on_msg_delete_req(m))
        r.action_edit.connect(lambda: self.on_msg_edit_req(m))
        idx = self.alay.count()-1 if index == -1 else index
        self.alay.insertWidget(idx, r)

    def _parse_message_content(self, m):
        rc = m.get('content','')
        ft = ""
        fa = m.get('attachments') or []
        if ATTACHMENT_SPLITTER in rc:
            p = rc.split(ATTACHMENT_SPLITTER)
            ft = p[0]
            for x in p[1:]: 
                if x.startswith("cmd://"): 
                    try:
                        t,u=x[6:].split("::",1)
                        fa.append({'type':t,'url':u})
                    except:
                        pass
        else:
            if rc.startswith("cmd://"): 
                try:
                    t,u=rc[6:].split("::",1)
                    fa.append({'type':t,'url':u})
                except:
                    ft = rc
            else:
                ft = rc
        return ft, fa

    def poll_new_messages(self):
        last = self.messages_list_data[-1]['id'] if self.messages_list_data else 0
        threading.Thread(target=self._worker_poll, args=(last,)).start()

    def _worker_poll(self, last):
        try:
            r=requests.get(f"{network.API_URL}/messages/load", params={"u1":self.current_user, "u2":self.active_chat_user, "last_id":last}, verify=False, timeout=4)
            if r.status_code == 200:
                msgs=r.json().get('messages', [])
                if msgs:
                    ids=[m['id'] for m in msgs if m['sender_name']!=self.current_user]
                    if ids:
                        requests.post(f"{network.API_URL}/messages/read", json={"ids":ids, "user":self.current_user}, verify=False)
                    QTimer.singleShot(0, lambda: self._append_new(msgs))
        except:
            pass

    def _append_new(self, msgs):
        if not msgs:
            return
        exist = {m['id'] for m in self.messages_list_data}
        uniq = [m for m in msgs if m['id'] not in exist]
        if not uniq:
            return
        self.messages_list_data.extend(uniq)
        self.loaded_count += len(uniq)
        
        last = uniq[-1]
        raw = last.get('content', '')
        ptxt = raw.split(ATTACHMENT_SPLITTER)[0] if ATTACHMENT_SPLITTER in raw else raw
        if "cmd://image" in raw and not ptxt:
            ptxt="🖼️ Изображение"
        elif "cmd://file" in raw and not ptxt:
            ptxt="📄 Документ"
        self._update_list_preview(self.active_chat_user, ptxt, last.get('created_at'))
        for m in uniq:
            self._add_bubble_to_ui(m)
        self.scroll_to_bottom()

    def send_text(self):
        t = self.inp.toPlainText().strip()
        has = len(self.pending_attachments)>0
        if not t and not has:
            return
        if not self.active_chat_user:
            return
        atts_ui = [{'type': a['type'], 'url': a['path']} for a in self.pending_attachments]
        atts_net = [{'path': a['path'], 'type': a['type']} for a in self.pending_attachments]
        self.inp.clear()
        self.clear_attachment_full()
        self.btn_send.animate_send()
        
        ts_now = datetime.datetime.now().isoformat()
        loc = {
            'id': -1, 'content': t, 'sender_name': self.current_user,
            'avatar_url': self.my_avatar_data, 'created_at': ts_now,
            'is_read': False, 'attachments': atts_ui
        }
        self._add_bubble_to_ui(loc)
        self.scroll_to_bottom()
        
        prev = t if t else ("🖼️ Изображение" if any(x['type']=='image' for x in atts_ui) else "📄 Документ")
        self._update_list_preview(self.active_chat_user, f"Вы: {prev}", ts_now)
        
        threading.Thread(target=task_batch_send, args=(self.current_user, self.active_chat_user, t, atts_net)).start()
        QTimer.singleShot(500, self.poll_new_messages)

    def on_msg_delete_req(self, m):
        mb = QMessageBox(self)
        mb.setWindowTitle("Удаление")
        mb.setText("Удалить сообщение?")
        b_me = mb.addButton("Только я", QMessageBox.ActionRole)
        b_all = mb.addButton("У всех", QMessageBox.DestructiveRole)
        mb.addButton("Отмена", QMessageBox.RejectRole)
        mb.exec()
        if mb.clickedButton() in (b_me, b_all):
            requests.post(f"{network.API_URL}/messages/delete_one", json={"id":m['id'],"for_all":(mb.clickedButton()==b_all),"user":self.current_user}, verify=False)
            QTimer.singleShot(200, self._load_initial_history)

    def on_msg_edit_req(self, m):
        t, _ = self._parse_message_content(m)
        nt, ok = QInputDialog.getMultiLineText(self, "Edit", "Text:", t)
        if ok and nt.strip():
            requests.post(f"{network.API_URL}/messages/edit", json={"id":m['id'],"new_text":nt,"user":self.current_user}, verify=False)
            QTimer.singleShot(200, self._load_initial_history)

    def scroll_to_bottom(self): 
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def clear_chat_area(self):
        while self.alay.count():
            item = self.alay.takeAt(0)
            if item.widget(): 
                item.widget().deleteLater()
        self.alay.addStretch()

    def closeEvent(self, e):
        self.chat_list_timer.stop()
        self.msg_poll_timer.stop()
        self.typing_poll_timer.stop()
        super().closeEvent(e)