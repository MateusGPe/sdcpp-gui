import queue
import threading
from collections import OrderedDict
from io import BytesIO
from typing import Any, Callable
from typing import OrderedDict as TOrderedDict
from typing import Tuple

import requests
from PIL import Image, ImageTk


class ImageLoader:
    """
    Helper to load images from URLs in a dedicated thread pool
    and cache them for Tkinter usage.
    """

    def __init__(self, max_cache_size: int = 200) -> None:
        """Logic: Initializes worker thread and cache."""
        self.queue: queue.Queue[
            Tuple[str, Callable[[Any], None], Tuple[int, int]]
        ] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.cache: TOrderedDict[str, Any] = OrderedDict()
        self.max_cache_size = max_cache_size
        self._cache_lock = threading.Lock()
        self.worker_thread.start()

    def request(
        self,
        url: str,
        callback: Callable[[Any], None],
        size: Tuple[int, int] = (150, 150),
    ) -> None:
        """
        Queues an image download request.

        Args:
            url: The URL of the image.
            callback: Function to call with the resulting ImageTk object.
            size: Tuple (width, height) to resize the image to.

        Logic: Checks cache or queues download request.
        """
        if not url:
            return
        with self._cache_lock:
            if url in self.cache:
                self.cache.move_to_end(url)
                callback(self.cache[url])
                return
        self.queue.put((url, callback, size))

    def _worker(self) -> None:
        """
        Background worker consuming the queue.
        Logic: Processes queue items: downloads image, resizes, caches,
        and executes callback.
        """
        with requests.Session() as sess:
            while not self.stop_event.is_set():
                try:
                    url, callback, size = self.queue.get(timeout=1)
                    tk_img = None
                    try:
                        with self._cache_lock:
                            cached = self.cache.get(url)
                        if cached:
                            tk_img = cached
                        else:
                            resp = sess.get(url, timeout=10)
                            if resp.status_code == 200:
                                img_data = BytesIO(resp.content)
                                pil_img = Image.open(img_data)
                                pil_img.thumbnail(size)
                                tk_img = ImageTk.PhotoImage(pil_img)
                                with self._cache_lock:
                                    self.cache[url] = tk_img
                                    self.cache.move_to_end(url)
                                    if len(self.cache) > self.max_cache_size:
                                        self.cache.popitem(last=False)
                        if tk_img:
                            self._safe_callback(callback, tk_img)
                    except Exception:
                        pass
                    finally:
                        self.queue.task_done()
                except queue.Empty:
                    pass

    def _safe_callback(self, cb: Callable[[Any], None], img: Any) -> None:
        """Executes callback safely suppressing exceptions.

        Logic: Executes callback handling exceptions."""
        try:
            cb(img)
        except Exception:
            pass

    def stop(self) -> None:
        """Stops the worker thread.

        Logic: Sets stop event."""
        self.stop_event.set()
