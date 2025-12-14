from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal

from client.widgets.messages_page.pages import MessagesPage
from client.widgets.settings_page import SettingsPage
from client.widgets.friends_page import FriendsPage
from client.widgets.profile_page import ProfilePage
from client.widgets.feed_page import FeedPage
from client.widgets.media_page import MediaPage

class ContentArea(QWidget):
    logout_requested = Signal()
    switch_user_requested = Signal(str)
    
    user_data_changed = Signal()

    def __init__(self, theme_manager):
        super().__init__()
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)

        self.st = QStackedWidget()

        self.pp = ProfilePage()
        self.fp = FeedPage()
        self.mp = MediaPage()
        self.fr = FriendsPage()
        self.msg = MessagesPage()
        self.sp = SettingsPage(theme_manager=theme_manager)
        
        self.sp.avatar_changed.connect(self.hdl_av)
        
        self.sp.profile_changed.connect(self.hdl_prof_txt)
        
        self.sp.out.connect(self.logout_requested.emit)
        self.sp.sw.connect(self.switch_user_requested.emit)
        self.fr.start_chat_requested.connect(self.go_chat)

        self.st.addWidget(self.pp)
        self.st.addWidget(self.fp)
        self.st.addWidget(self.mp)
        self.st.addWidget(self.fr)
        self.st.addWidget(self.msg)
        self.st.addWidget(self.sp)

        l.addWidget(self.st)

    def hdl_av(self):
        self.user_data_changed.emit()
        self.pp.refresh()

    def hdl_prof_txt(self):
        self.pp.refresh()

    def set_user(self, u):
        self.msg.set_current_user(u)
        self.fr.set_user(u)
        self.sp.set_user(u)
        self.pp.set_user(u)
        self.mp.set_user(u)

    def show_profile(self):
        self.st.setCurrentIndex(0)

    def show_feed(self):
        self.st.setCurrentIndex(1)

    def show_media(self):
        self.st.setCurrentIndex(2)

    def show_friends(self):
        self.st.setCurrentIndex(3)
        self.fr.load_friends()

    def show_messages(self):
        self.st.setCurrentIndex(4)

    def show_settings(self):
        self.st.setCurrentIndex(5)

    def go_chat(self, u):
        self.show_messages()
        self.msg.start_chat_with_user(u)