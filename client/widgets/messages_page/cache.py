import threading
import base64
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QMovie

class ImageCache:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._pixmap_cache = {}
                cls._instance._movie_cache = {}
                cls._instance._max_size = 150
            return cls._instance

    def get_pixmap(self, key, data=None, load_func=None):
        if key not in self._pixmap_cache:
            if data:
                pm = QPixmap()
                pm.loadFromData(data)
                if not pm.isNull():
                    self._check_limit()
                    self._pixmap_cache[key] = pm
            elif load_func:
                pm = load_func()
                if pm and not pm.isNull():
                    self._check_limit()
                    self._pixmap_cache[key] = pm
        return self._pixmap_cache.get(key)

    def _check_limit(self):
        if len(self._pixmap_cache) >= self._instance._max_size:
            self._pixmap_cache.pop(next(iter(self._pixmap_cache)))

    def get_movie(self, key, buffer):
        if key not in self._movie_cache:
            movie = QMovie(buffer, QByteArray())
            if movie.isValid():
                movie.setCacheMode(QMovie.CacheAll)
                if len(self._movie_cache) >= self._instance._max_size:
                    k = next(iter(self._movie_cache))
                    self._movie_cache[k].stop()
                    self._movie_cache.pop(k)
                self._movie_cache[key] = movie
        return self._movie_cache.get(key)