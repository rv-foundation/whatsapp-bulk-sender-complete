from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QProgressBar, QLineEdit,
    QFileDialog, QTextEdit, QVBoxLayout, QHBoxLayout, QSpinBox, QCheckBox
)
from PySide6.QtGui import QIcon

class Ui_MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WhatsApp Bulk Sender - Dashboard")
        self.setGeometry(400, 200, 700, 560)
        layout = QVBoxLayout()

        # file selectors
        self.contacts_btn = QPushButton("Select Contacts Excel (.xlsx)")
        self.contacts_lbl = QLabel("No file selected")

        self.message_btn = QPushButton("Select Message template (.txt)")
        self.message_lbl = QLabel("No file selected")

        self.image_btn = QPushButton("Select Image to send")
        self.image_lbl = QLabel("No file selected")

        layout.addWidget(self.contacts_btn)
        layout.addWidget(self.contacts_lbl)
        layout.addWidget(self.message_btn)
        layout.addWidget(self.message_lbl)
        layout.addWidget(self.image_btn)
        layout.addWidget(self.image_lbl)

        # controls
        control_row = QHBoxLayout()
        self.limit_input = QSpinBox()
        self.limit_input.setRange(50, 2000)
        self.limit_input.setValue(300)
        self.pause_every = QSpinBox()
        self.pause_every.setRange(5, 500)
        self.pause_every.setValue(25)
        self.pause_min = QSpinBox()
        self.pause_min.setRange(10, 600)
        self.pause_min.setValue(60)
        self.pause_max = QSpinBox()
        self.pause_max.setRange(10, 1200)
        self.pause_max.setValue(180)
        self.resume_chk = QCheckBox("Resume where left off")
        self.resume_chk.setChecked(True)

        control_row.addWidget(QLabel("Daily limit"))
        control_row.addWidget(self.limit_input)
        control_row.addWidget(QLabel("Auto-pause every"))
        control_row.addWidget(self.pause_every)
        control_row.addWidget(QLabel("Pause min (s)"))
        control_row.addWidget(self.pause_min)
        control_row.addWidget(QLabel("Pause max (s)"))
        control_row.addWidget(self.pause_max)
        layout.addLayout(control_row)
        layout.addWidget(self.resume_chk)

        # start/stop buttons
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("START SENDING")
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

        # progress and logs
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.status_lbl = QLabel("Idle")

        layout.addWidget(QLabel("Progress:"))
        layout.addWidget(self.progress)
        layout.addWidget(QLabel("Log:"))
        layout.addWidget(self.log)
        layout.addWidget(self.status_lbl)

        self.setLayout(layout)
