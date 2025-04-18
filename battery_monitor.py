import sys
import psutil
import time
import queue
from threading import Thread
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                             QSpinBox, QLabel, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from win10toast import ToastNotifier
import os

class NotificationManager:
    def __init__(self):
        self.toaster = ToastNotifier()
        self.queue = queue.Queue()
        self.worker = Thread(target=self.run)
        self.worker.daemon = True
        self.worker.start()

    def run(self):
        while True:
            title, message = self.queue.get()
            try:
                self.toaster.show_toast(title, message, duration=10)
            except Exception as e:
                print(f"Notification error: {e}")
            self.queue.task_done()

    def send(self, title, message):
        self.queue.put((title, message))


class BatteryMonitor(QThread):
    battery_status = pyqtSignal(int, bool)

    def __init__(self, threshold, notifier):
        super().__init__()
        self.threshold = threshold
        self.running = True
        self.notifier = notifier

    def run(self):
        while self.running:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                charging = battery.power_plugged
                self.battery_status.emit(percent, charging)
                if charging and percent >= self.threshold:
                    self.notifier.send(
                        "Battery Alert 🔋",
                        f"Battery is at {percent}%. You should unplug the charger."
                    )

            # Responsive sleep: checks every second to allow faster shutdown
            for _ in range(30):
                if not self.running:
                    return
                time.sleep(1)

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

    def update_threshold(self, new_threshold):
        self.threshold = new_threshold
        print(f"Threshold updated to {new_threshold}%")


class BatteryMonitorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.notifier = NotificationManager()
        self.monitor_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Battery Monitor')
        self.setGeometry(300, 300, 300, 200)

        layout = QVBoxLayout()

        self.threshold_label = QLabel('Set Notification Threshold (%):', self)
        layout.addWidget(self.threshold_label)

        self.threshold_input = QSpinBox(self)
        self.threshold_input.setRange(1, 100)
        self.threshold_input.setValue(60)
        layout.addWidget(self.threshold_input)

        self.update_threshold_button = QPushButton('Update Threshold', self)
        self.update_threshold_button.clicked.connect(self.applyThreshold)
        layout.addWidget(self.update_threshold_button)

        self.start_button = QPushButton('Start Monitoring', self)
        self.start_button.clicked.connect(self.startMonitoring)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton('Stop Monitoring', self)
        self.stop_button.clicked.connect(self.stopMonitoring)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.setLayout(layout)

        self.tray_icon = QSystemTrayIcon(self)
        # Get the directory where your script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Create absolute path to the icon file
        icon_path = os.path.join(script_dir, "Battery_icon.ico")

        # Use the absolute path for the icon
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip('Battery Monitor')

        tray_menu = QMenu(self)
        restore_action = QAction('Restore', self)
        restore_action.triggered.connect(self.show)
        tray_menu.addAction(restore_action)

        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.exitApp)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.trayIconActivated)
        self.tray_icon.show()
        self.startMonitoring()

    def startMonitoring(self):
        threshold = self.threshold_input.value()
        self.monitor_thread = BatteryMonitor(threshold, self.notifier)
        self.monitor_thread.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stopMonitoring(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def applyThreshold(self):
        if self.monitor_thread:
            new_threshold = self.threshold_input.value()
            self.monitor_thread.update_threshold(new_threshold)
        else:
            print("Monitoring not active. Start monitoring first.")

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def trayIconActivated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()

    def exitApp(self):
        self.stopMonitoring()
        QApplication.quit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    ex = BatteryMonitorApp()
    ex.show()
    sys.exit(app.exec_())
