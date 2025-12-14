import requests
import functools
import threading
import concurrent.futures
from collections import defaultdict
from PySide6.QtCore import QRunnable, Signal, QObject, QThreadPool
from PySide6.QtGui import QImage
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://localhost:8001"
ATTACHMENT_SPLITTER = "<<<SPLIT>>>"

class ThreadPoolManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # max_workers=4 чтобы не забивать IO
                cls._instance._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="net_worker")
                cls._instance._current_context_id = 0 # <-- ID текущей сессии
            return cls._instance

    def submit(self, username_context, task_func, *args, **kwargs):
        # Оборачиваем задачу, чтобы она знала, в какой сессии она запущена
        context_id = self._current_context_id
        
        def safe_wrapper():
            # Если сессия сменилась (ID не совпадает), не выполняем задачу (или не эмитим результат)
            if self._current_context_id != context_id:
                return
            try:
                task_func(*args, **kwargs)
            except:
                pass

        return self._executor.submit(safe_wrapper)

    def clear_all_tasks(self):
        """Инвалидирует (отменяет) все текущие задачи в очереди"""
        # Мы просто меняем ID контекста. Старые задачи увидят старый ID и сделают return.
        self._current_context_id += 1

@functools.lru_cache(maxsize=128)
def fetch_avatar_data(username):
    try:
        r = requests.get(f"{API_URL}/user/profile_info", params={"username": username}, verify=False, timeout=3)
        if r.status_code == 200:
            return r.json().get('avatar_url')
    except:
        pass
    return None

def fetch_full_profile(username):
    try:
        r = requests.get(f"{API_URL}/user/profile_info", params={"username": username}, verify=False, timeout=3)
        if r.status_code == 200:
            res = r.json()
            res['username'] = username
            return res
    except:
        pass
    return None

@functools.lru_cache(maxsize=64)
def fetch_chat_data(username):
    try:
        r = requests.get(f"{API_URL}/contacts/list", params={"username": username}, verify=False, timeout=3)
        if r.status_code == 200:
            return tuple(r.json().get('contacts', []))
    except:
        pass
    return tuple()

def task_batch_send(sender_u, receiver_u, text_content, attachments):
    try:
        parts = [text_content if text_content else ""]
        if attachments:
            for item in attachments:
                parts.append(f"cmd://{item['type']}::{item['path']}")
        combined = ATTACHMENT_SPLITTER.join(parts)
        if not combined.strip():
            return
        requests.post(f"{API_URL}/messages/send", json={"to_user": receiver_u, "text": combined}, params={"sender": sender_u}, verify=False, timeout=15)
    except:
        pass

class HeaderResultSignaler(QObject):
    updated = Signal(dict)

class WorkerSignals(QObject):
    loaded = Signal(object)
    finished = Signal()

class ChatLoaderSignals(QObject):
    loaded = Signal(list)

class ChatLoader(QRunnable):
    def __init__(self, username):
        super().__init__()
        self.u = username
        self.signals = ChatLoaderSignals()

    def run(self):
        data = fetch_chat_data(self.u)
        self.signals.loaded.emit(list(data) if data else [])

class HistorySignals(QObject):
    result_ready = Signal(list, int)
    finished = Signal()

class HistoryLoader(QRunnable):
    def __init__(self, u1, u2, off=0, lim=50):
        super().__init__()
        self.u1 = u1
        self.u2 = u2
        self.off = off
        self.lim = lim
        self.signals = HistorySignals()

    def run(self):
        msgs = []
        try:
            r = requests.get(f"{API_URL}/messages/history", params={"u1": self.u1, "u2": self.u2, "offset": self.off, "limit": self.lim}, verify=False, timeout=5)
            if r.status_code == 200:
                msgs = r.json().get('messages', [])
                if self.off == 0 and msgs:
                    tr = [m['id'] for m in msgs if m['sender_name'] != self.u1 and not m['is_read']]
                    if tr:
                        requests.post(f"{API_URL}/messages/read", json={"ids": tr, "user": self.u1}, verify=False)
        except:
            pass
        self.signals.result_ready.emit(msgs, self.off)
        self.signals.finished.emit()

class ImgSignals(QObject):
    loaded = Signal(object)

class DataSignals(QObject):
    loaded = Signal(bytes)

class DataLoader(QRunnable):
    """ Loads raw bytes (allows GIF animation) handling relative URLs """
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = DataSignals()
        self.loaded = self.signals.loaded 
        self.setAutoDelete(True)

    def run(self):
        if not self.url:
            self.signals.loaded.emit(b"")
            return
        try:
            target = str(self.url)
            # Если это путь на диске
            if os.path.exists(target):
                with open(target, 'rb') as f:
                    self.signals.loaded.emit(f.read())
            else:
                # Если это сетевой путь
                if target.startswith("/"):
                    target = f"{API_URL}{target}"
                
                if target.startswith("http"):
                    r = requests.get(target, verify=False, timeout=10)
                    if r.status_code == 200:
                        self.signals.loaded.emit(r.content)
                    else:
                        self.signals.loaded.emit(b"")
                else:
                    self.signals.loaded.emit(b"")
        except:
            self.signals.loaded.emit(b"")
            
    def start(self):
        QThreadPool.globalInstance().start(self)

class ChatImageLoader(QRunnable):
    """ Loads QImage (for static processing/thumbnails), handling relative URLs """
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = ImgSignals()
        self.loaded = self.signals.loaded 
        self.setAutoDelete(True)

    def run(self):
        if not self.url:
            self.signals.loaded.emit(None)
            return
        try:
            target = str(self.url)
            # Local
            if os.path.exists(target):
                img = QImage()
                img.load(target)
                if not img.isNull():
                    self.signals.loaded.emit(img)
                else:
                    self.signals.loaded.emit(None)
            else:
                # Remote
                if target.startswith("/"):
                    target = f"{API_URL}{target}"
                
                if target.startswith("http"):
                    r = requests.get(target, verify=False, timeout=10)
                    if r.status_code == 200:
                        img = QImage()
                        img.loadFromData(r.content)
                        self.signals.loaded.emit(img if not img.isNull() else None)
                    else:
                        self.signals.loaded.emit(None)
                else:
                    self.signals.loaded.emit(None)
        except:
            self.signals.loaded.emit(None)

    def start(self):
        QThreadPool.globalInstance().start(self)