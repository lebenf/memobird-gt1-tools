#!/usr/bin/env python3
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QCheckBox, QFileDialog, QProgressBar, QFrame
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from PIL import Image, ImageQt
from memobird_driver import MemobirdGT1

MAC = os.environ.get("MEMOBIRD_MAC", "00:15:83:41:D3:9C")


class PrintThread(QThread):
    finished = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, image_path, dither):
        super().__init__()
        self.image_path = image_path
        self.dither = dither

    def run(self):
        try:
            self.progress.emit("Connessione...")
            with open(self.image_path, "rb") as f:
                img_data = f.read()
            with MemobirdGT1(mac=MAC) as printer:
                self.progress.emit("Invio immagine...")
                printer.print_image(img_data, dither=self.dither)
            self.finished.emit("ok")
        except Exception as e:
            self.finished.emit(f"err:{e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Memobird GT1 - Stampa immagine")
        self.setMinimumWidth(420)
        self.image_path = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Anteprima
        self.preview = QLabel("Nessuna immagine selezionata")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(280)
        self.preview.setStyleSheet("background:#1a1a1a; border-radius:6px; color:#888;")
        layout.addWidget(self.preview)

        # Pulsante scegli
        btn_pick = QPushButton("Scegli immagine…")
        btn_pick.setFixedHeight(36)
        btn_pick.clicked.connect(self.pick_image)
        layout.addWidget(btn_pick)

        # Separatore
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#333;")
        layout.addWidget(line)

        # Opzioni
        options = QHBoxLayout()
        self.chk_dither = QCheckBox("Dithering (migliore per foto)")
        self.chk_dither.setChecked(True)
        options.addWidget(self.chk_dither)
        options.addStretch()
        layout.addLayout(options)

        # Stampa
        self.btn_print = QPushButton("Stampa")
        self.btn_print.setFixedHeight(40)
        self.btn_print.setEnabled(False)
        self.btn_print.setStyleSheet(
            "QPushButton { background:#2a7fd4; color:white; border-radius:6px; font-weight:bold; font-size:14px; }"
            "QPushButton:disabled { background:#333; color:#666; }"
            "QPushButton:hover { background:#3a8fe4; }"
        )
        self.btn_print.clicked.connect(self.do_print)
        layout.addWidget(self.btn_print)

        # Stato
        self.status = QLabel("Pronto")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color:#888; font-size:12px;")
        layout.addWidget(self.status)

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Scegli immagine", "",
            "Immagini (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff)"
        )
        if not path:
            return
        self.image_path = path
        self.update_preview(path)
        self.btn_print.setEnabled(True)
        self.status.setText(os.path.basename(path))

    def update_preview(self, path):
        img = Image.open(path).convert("RGB")
        # Mostra anteprima in bianco/nero come verrà stampata
        preview_img = img.copy()
        preview_img.thumbnail((380, 270), Image.Resampling.LANCZOS)
        qimg = QImage(
            preview_img.tobytes("raw", "RGB"),
            preview_img.width, preview_img.height,
            preview_img.width * 3,
            QImage.Format.Format_RGB888
        )
        self.preview.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                380, 270,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )

    def do_print(self):
        self.btn_print.setEnabled(False)
        self.status.setText("Stampa in corso…")
        self.thread = PrintThread(self.image_path, self.chk_dither.isChecked())
        self.thread.progress.connect(self.status.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def on_finished(self, result):
        self.btn_print.setEnabled(True)
        if result == "ok":
            self.status.setStyleSheet("color:#4caf50; font-size:12px;")
            self.status.setText("Stampato!")
        else:
            msg = result.replace("err:", "")
            self.status.setStyleSheet("color:#f44336; font-size:12px;")
            self.status.setText(f"Errore: {msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
