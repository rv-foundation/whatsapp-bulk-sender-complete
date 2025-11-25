import sys
import threading
import asyncio
from pathlib import Path
from PySide6.QtWidgets import QApplication, QFileDialog
from ui_main import Ui_MainWindow
from path_utils import base_path
from sender import send_batch

def run_async_in_thread(coro):
    """Run given coroutine in a new asyncio loop inside a background thread."""
    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t

class MainApp(Ui_MainWindow):
    def __init__(self):
        super().__init__()
        bp = base_path()
        # default bundled files
        self.default_message = str(bp / 'message.txt')
        self.default_image = str(bp / 'image.jpg')

        self.contacts_btn.clicked.connect(self.pick_contacts)
        self.message_btn.clicked.connect(self.pick_message)
        self.image_btn.clicked.connect(self.pick_image)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)

        self._running = False

    def pick_contacts(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Contacts Excel", "", "Excel Files (*.xlsx)")
        if f:
            self.contacts_lbl.setText(f)
            self.contacts_file = f

    def pick_message(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Message .txt", "", "Text Files (*.txt)")
        if f:
            self.message_lbl.setText(f)
            self.message_file = f

    def pick_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.jpg *.png *.jpeg)")
        if f:
            self.image_lbl.setText(f)
            self.image_file = f

    def append_log(self, text):
        self.log.append(text)

    def start(self):
        if getattr(self, 'contacts_file', None) is None:
            self.append_log('Please select contacts Excel file first.')
            return
        msg_file = getattr(self, 'message_file', None) or self.default_message
        img_file = getattr(self, 'image_file', None) or self.default_image
        limit = int(self.limit_input.value())
        pause_every = int(self.pause_every.value())
        pause_min = int(self.pause_min.value())
        pause_max = int(self.pause_max.value())
        resume = bool(self.resume_chk.isChecked())

        # disable UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._running = True

        coro = send_batch(
            gui=self,
            excel_path=self.contacts_file,
            template_path=msg_file,
            image_path=img_file,
            daily_limit=limit,
            min_delay=6.0,
            max_delay=12.0,
            auto_pause_every=pause_every,
            auto_pause_min=pause_min,
            auto_pause_max=pause_max,
            resume=resume
        )
        run_async_in_thread(coro)

    def stop(self):
        self.append_log('STOP requested. To fully stop, close browser window. (Graceful cancellation not implemented)')
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        self._running = False

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
