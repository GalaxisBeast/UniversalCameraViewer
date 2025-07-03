import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QMessageBox
from PyQt5.QtMultimedia import QCamera, QMediaDevices
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtCore import Qt

class TestCamera(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Camera")
        self.resize(800, 600)

        layout = QVBoxLayout()
        self.viewfinder = QCameraViewfinder()
        self.viewfinder.setAspectRatioMode(Qt.KeepAspectRatio)
        layout.addWidget(self.viewfinder)
        self.setLayout(layout)

        cameras = QMediaDevices.videoInputs()
        if not cameras:
            QMessageBox.critical(self, "Error", "No cameras found")
            sys.exit(1)

        self.camera = QCamera(cameras[0])
        self.camera.setViewfinder(self.viewfinder)
        self.camera.errorOccurred.connect(self.camera_error)
        self.camera.start()

    def camera_error(self, error, errorString):
        QMessageBox.critical(self, "Camera error", errorString)
        sys.exit(1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestCamera()
    window.show()
    sys.exit(app.exec_())
