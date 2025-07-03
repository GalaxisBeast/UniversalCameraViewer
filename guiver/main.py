import sys
import time
import cv2
import sounddevice as sd
from pygrabber.dshow_graph import FilterGraph
from PyQt5.QtWidgets import (
    QApplication, QLabel, QWidget, QVBoxLayout, QMessageBox, QInputDialog, QTextEdit
)
from PyQt5.QtGui import QImage, QPixmap, QTextCursor
from PyQt5.QtCore import Qt, QThread, pyqtSignal

import numpy as np

try:
    import rtmixer
except ImportError:
    rtmixer = None
    print("Warning: python-rtmixer not installed. Advanced Windows audio APIs won't be available.")

#########################
# Debug Window
#########################
class DebugWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Debug Console - FPS: N/A")
        self.resize(600, 300)
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

        self.capture_window_ref = None

    def append_message(self, msg):
        self.text_edit.append(msg)
        self.text_edit.moveCursor(QTextCursor.End)

    def update_fps(self, fps):
        self.setWindowTitle(f"Debug Console - FPS: {fps:.2f}")

    def closeEvent(self, event):
        if self.capture_window_ref and self.capture_window_ref.isVisible():
            self.capture_window_ref.close()
        QApplication.quit()
        event.accept()

#########################
# Audio Thread using sounddevice (fallback)
#########################
class AudioStreamSD(QThread):
    debug = pyqtSignal(str)

    def __init__(self, device_index):
        super().__init__()
        self.device_index = device_index
        self.running = True

    def run(self):
        def callback(indata, outdata, frames, time, status):
            if status:
                self.debug.emit(f"Audio Status: {status}")
            outdata[:] = indata

        self.debug.emit(f"Starting sounddevice audio stream on device index {self.device_index} with low latency...")
        try:
            with sd.Stream(device=(self.device_index, self.device_index), channels=1, callback=callback, latency='low'):
                self.debug.emit("Sounddevice audio stream started successfully.")
                while self.running:
                    sd.sleep(100)
        except Exception as e:
            self.debug.emit(f"Sounddevice audio stream error: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

#########################
# Audio Thread using python-rtmixer (advanced Windows APIs)
#########################
class AudioStreamRTMixer(QThread):
    debug = pyqtSignal(str)

    def __init__(self, device_index, api):
        super().__init__()
        self.device_index = device_index
        self.api = api
        self.running = True
        self.mixer = None

    def audio_callback(self, input_data, frame_count, time_info, status):
        if status:
            self.debug.emit(f"RTMixer audio callback status: {status}")
        # input_data is bytes, do nothing or processing here
        # just pass, no output since input only
        return None, rtmixer.RtAudioCallbackResult.Continue

    def run(self):
        if rtmixer is None:
            self.debug.emit("python-rtmixer not installed! Cannot start RTMixer audio stream.")
            return

        self.debug.emit(f"Starting RTMixer audio stream on device index {self.device_index} with API {self.api.name}...")

        try:
            self.mixer = rtmixer.RtMixer(input_device=self.device_index,
                                         output_device=None,
                                         channels=1,
                                         sample_rate=44100,
                                         buffer_size=256,
                                         api=self.api)
            self.mixer.start_stream(self.audio_callback)
            self.debug.emit("RTMixer audio stream started successfully.")
            while self.running and self.mixer.is_stream_running():
                time.sleep(0.1)
        except Exception as e:
            self.debug.emit(f"RTMixer audio stream error: {e}")

    def stop(self):
        self.running = False
        if self.mixer is not None and self.mixer.is_stream_running():
            self.mixer.stop_stream()
            self.mixer.close()
        self.quit()
        self.wait()

#########################
# Video thread (same as before)
#########################
class VideoThread(QThread):
    change_pixmap = pyqtSignal(QPixmap)
    debug = pyqtSignal(str)
    fps_updated = pyqtSignal(float)

    def __init__(self, device_index):
        super().__init__()
        self.device_index = device_index
        self.running = True

    def run(self):
        self.debug.emit(f"Trying to open video device {self.device_index} with CAP_DSHOW...")
        cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.debug.emit(f"CAP_DSHOW failed, trying CAP_MSMF for device {self.device_index}...")
            cap = cv2.VideoCapture(self.device_index, cv2.CAP_MSMF)
        if not cap.isOpened():
            self.debug.emit(f"Failed to open camera device {self.device_index} with both CAP_DSHOW and CAP_MSMF.")
            return
        self.debug.emit(f"Camera device {self.device_index} opened successfully.")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 60)

        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.debug.emit(f"Requested resolution and FPS:")
        self.debug.emit(f"  Width: {w}")
        self.debug.emit(f"  Height: {h}")
        self.debug.emit(f"  FPS: {fps}")

        prev_time = time.time()
        frame_count = 0

        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                self.msleep(10)
                continue

            frame_count += 1
            curr_time = time.time()
            elapsed = curr_time - prev_time

            if elapsed >= 1.0:
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                self.fps_updated.emit(actual_fps)
                if actual_fps < 30:
                    self.debug.emit(f"Warning: Low FPS detected: {actual_fps:.2f}")
                prev_time = curr_time
                frame_count = 0

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            self.change_pixmap.emit(pixmap)

        cap.release()
        self.debug.emit("Video thread stopped and camera released.")

    def stop(self):
        self.running = False
        self.wait()

#########################
# Capture window (same as before)
#########################
class CaptureWindow(QWidget):
    def __init__(self, video_index, audio_thread, debug_window):
        super().__init__()
        self.audio_thread = audio_thread
        self.debug_window = debug_window
        self.debug_window_ref = debug_window

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
        self.thread.debug.connect(self.debug_window.append_message)
        self.thread.fps_updated.connect(self.debug_window.update_fps)
        self.thread.start()

    def update_image(self, pixmap):
        scaled = pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled)

    def closeEvent(self, event):
        self.debug_window.append_message("Stopping video thread...")
        self.thread.stop()
        self.debug_window.append_message("Stopping audio thread...")
        self.audio_thread.stop()
        self.audio_thread.wait()
        self.debug_window.append_message("Exiting application...")

        if self.debug_window_ref.isVisible():
            self.debug_window_ref.close()

        QApplication.quit()
        event.accept()

#########################
# Device enumeration
#########################

def list_video_devices_with_names():
    graph = FilterGraph()
    devices = graph.get_input_devices()
    return devices

def get_hostapi_indices_sd():
    # sounddevice host api indices keyed by lowercase name
    return {h['name'].lower(): i for i, h in enumerate(sd.query_hostapis())}

def get_rtmixer_api_by_name(name):
    if not rtmixer:
        return None
    for api in rtmixer.Api:
        if api.name.lower() == name.lower():
            return api
    return None

def list_rtmixer_devices_by_apis(preferred_api_names):
    """
    List devices from rtmixer for the specified Windows APIs (ASIO, WASAPI, WDM-KS, DirectSound).
    Returns lists: devices, names, indices, api_enum
    """
    if not rtmixer:
        return [], [], [], []

    devices = []
    names = []
    indices = []
    apis = []

    for api_name in preferred_api_names:
        api = get_rtmixer_api_by_name(api_name)
        if api is None:
            continue
        mixer = rtmixer.RtMixer(api=api)
        for i in range(mixer.get_device_count()):
            info = mixer.get_device_info(i)
            if info['inputChannels'] > 0:
                devices.append(info)
                names.append(f"{info['name']} ({api_name})")
                indices.append(i)
                apis.append(api)
        mixer.close()
    return devices, names, indices, apis

def list_audio_input_devices_filtered():
    """
    Fallback filtered devices from sounddevice with host API name appended.
    Returns devices, names, indices (in sounddevice global devices)
    """
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    filtered_devices = []
    filtered_names = []
    filtered_indices = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0 and (
            'elgato' in dev['name'].lower() or
            'avermedia' in dev['name'].lower() or
            'evga' in dev['name'].lower()
        ):
            api_name = hostapis[dev['hostapi']]['name']
            filtered_devices.append(dev)
            filtered_names.append(f"{dev['name']} ({api_name})")
            filtered_indices.append(i)
    return filtered_devices, filtered_names, filtered_indices

def prompt_selection_gui(options, device_type):
    items = [f"{i}: {name}" for i, name in enumerate(options)]
    item, ok = QInputDialog.getItem(None, f"Select {device_type} Device",
                                    f"Choose a {device_type} device:", items, 0, False)
    if ok and item:
        return int(item.split(":")[0])
    else:
        QMessageBox.critical(None, "Error", f"No {device_type} device selected. Exiting.")
        sys.exit(1)

#########################
# Main app
#########################

def main():
    app = QApplication(sys.argv)

    debug_window = DebugWindow()
    debug_window.show()

    video_devices = list_video_devices_with_names()
    if not video_devices:
        debug_window.append_message("No video devices detected. Exiting.")
        sys.exit(1)
    video_choice = prompt_selection_gui(video_devices, "video")

    # Preferred Windows APIs for rtmixer:
    preferred_api_names = ['ASIO', 'WASAPI', 'WDM-KS', 'DirectSound']

    # List rtmixer devices first
    rtmixer_devices, rtmixer_names, rtmixer_indices, rtmixer_apis = list_rtmixer_devices_by_apis(preferred_api_names)

    # Fallback filtered devices from sounddevice
    fallback_devices, fallback_names, fallback_indices = list_audio_input_devices_filtered()

    # Combine the two lists with marking source
    all_audio_names = []
    device_source = []  # 'rtmixer' or 'sounddevice'
    # Add rtmixer devices
    for name in rtmixer_names:
        all_audio_names.append(name + " [RtMixer]")
        device_source.append('rtmixer')
    # Add fallback devices
    for name in fallback_names:
        all_audio_names.append(name + " [SoundDevice]")
        device_source.append('sounddevice')

    if not all_audio_names:
        debug_window.append_message("No audio input devices found. Exiting.")
        sys.exit(1)

    audio_choice = prompt_selection_gui(all_audio_names, "audio input")

    if device_source[audio_choice] == 'rtmixer':
        audio_thread = AudioStreamRTMixer(rtmixer_indices[audio_choice], rtmixer_apis[audio_choice])
    else:
        # fallback device index in sounddevice global devices
        # fallback indices are after rtmixer devices, so subtract offset
        fallback_index = audio_choice - len(rtmixer_indices)
        audio_thread = AudioStreamSD(fallback_indices[fallback_index])

    debug_window.append_message(f"Opening video device '{video_devices[video_choice]}' and audio device '{all_audio_names[audio_choice]}'...")

    audio_thread.debug.connect(debug_window.append_message)
    audio_thread.start()

    window = CaptureWindow(video_choice, audio_thread, debug_window)

    debug_window.capture_window_ref = window
    window.debug_window_ref = debug_window

    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
