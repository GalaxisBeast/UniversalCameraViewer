import sys
import cv2
import sounddevice as sd
from pygrabber.dshow_graph import FilterGraph
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QMessageBox
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal


class AudioStream(QThread):
    def __init__(self, device_index):
        super().__init__()
        self.device_index = device_index
        self.running = True

    def run(self):
        def callback(indata, outdata, frames, time, status):
            if status:
                print(f"Audio Status: {status}")
            outdata[:] = indata

        print(f"Starting audio stream on device index {self.device_index}...")
        try:
            with sd.Stream(device=(self.device_index, None), channels=1, callback=callback):
                print("Audio stream started successfully.")
                while self.running:
                    sd.sleep(100)
        except Exception as e:
            print(f"Audio stream error: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class VideoThread(QThread):
    change_pixmap = pyqtSignal(QPixmap)

    def __init__(self, device_index):
        super().__init__()
        self.device_index = device_index
        self.running = True

    def run(self):
        print(f"Trying to open video device {self.device_index} with CAP_DSHOW...")
        cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"CAP_DSHOW failed, trying CAP_MSMF for device {self.device_index}...")
            cap = cv2.VideoCapture(self.device_index, cv2.CAP_MSMF)
        if not cap.isOpened():
            print(f"Failed to open camera device {self.device_index} with both CAP_DSHOW and CAP_MSMF.")
            return
        print(f"Camera device {self.device_index} opened successfully.")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 60)

        print("Requested resolution and FPS:")
        print("  Width:", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        print("  Height:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print("  FPS:", cap.get(cv2.CAP_PROP_FPS))

        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                self.msleep(10)
                continue
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            self.change_pixmap.emit(pixmap)

        cap.release()
        print("Video thread stopped and camera released.")

    def stop(self):
        self.running = False
        self.wait()


class CaptureWindow(QWidget):
    def __init__(self, video_index, audio_thread):
        super().__init__()
        self.audio_thread = audio_thread
        self.setWindowTitle("Capture Card Viewer")
        self.resize(960, 540)
        self.setStyleSheet("background-color: black;")

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.thread = VideoThread(video_index)
        self.thread.change_pixmap.connect(self.update_image)
        self.thread.start()

    def update_image(self, pixmap):
        scaled = pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled)

    def closeEvent(self, event):
        print("Stopping video thread...")
        self.thread.stop()
        print("Stopping audio thread...")
        self.audio_thread.stop()
        self.audio_thread.wait()
        print("Exiting application...")
        QApplication.quit()
        event.accept()


def list_video_devices_with_names():
    graph = FilterGraph()
    devices = graph.get_input_devices()
    print("\nVideo Devices:")
    for i, name in enumerate(devices):
        print(f"{i}: {name}")
    if not devices:
        print("No video devices found.")
    return devices


def list_audio_input_devices_filtered():
    devices = sd.query_devices()
    filtered_devices = []
    filtered_names = []
    print("\nAudio Input Devices:")
    for dev in devices:
        if dev['max_input_channels'] > 0 and ('elgato' in dev['name'].lower() or 'avermedia' in dev['name'] or 'evga' in dev['name'].lower()):
            filtered_devices.append(dev)
            filtered_names.append(dev['name'])

    if not filtered_devices:
        print("No matching audio input devices found.")
        return [], []

    for i, name in enumerate(filtered_names):
        print(f"{i}: {name}")
    return filtered_devices, filtered_names


def prompt_selection(max_index, device_type):
    while True:
        try:
            choice = int(input(f"Select {device_type} device number: "))
            if 0 <= choice < max_index:
                return choice
            else:
                print("Invalid selection. Please enter one of the listed numbers.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def main():
    video_devices = list_video_devices_with_names()
    if not video_devices:
        print("No video devices detected. Exiting.")
        return
    video_choice = prompt_selection(len(video_devices), "video")

    audio_devices, audio_names = list_audio_input_devices_filtered()
    if not audio_devices:
        print("No matching audio input devices detected. Exiting.")
        return
    audio_choice_index = prompt_selection(len(audio_devices), "audio input")

    # Get the global device index of chosen filtered device
    all_devices = sd.query_devices()
    audio_choice_device_index = all_devices.index(audio_devices[audio_choice_index])

    print(f"\nOpening video device '{video_devices[video_choice]}' and audio device '{audio_names[audio_choice_index]}'...")

    app = QApplication(sys.argv)

    audio_thread = AudioStream(audio_choice_device_index)
    audio_thread.start()

    window = CaptureWindow(video_choice, audio_thread)
    window.show()

    exit_code = app.exec_()

    # No need to stop threads here, already handled in closeEvent
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
