"""Task: run a function off the UI thread."""
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication


class Task(QThread):
    """Run fn() off the UI thread; result arrives via done. Owned by the app and deleted once finished, so
    closing the window that started it can't destroy a running thread (that aborts the interpreter)."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__(QApplication.instance())
        self.fn = fn
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            self.failed.emit(str(e))
