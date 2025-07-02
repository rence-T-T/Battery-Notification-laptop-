import sys
import psutil
import time
import queue
import winsound
from threading import Thread
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                             QSpinBox, QLabel, QSystemTrayIcon, QMenu, QAction, QHBoxLayout)
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
            title, message, play_sound = self.queue.get()
            try:
                if play_sound:
                    # Play system notification sound BEFORE showing toast
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                self.toaster.show_toast(title, message, duration=10)
            except Exception as e:
                print(f"Notification error: {e}")
            self.queue.task_done()

    def send(self, title, message, play_sound=True):
        self.queue.put((title, message, play_sound))


class BatteryMonitor(QThread):
    battery_status = pyqtSignal(int, bool)

    def __init__(self, high_threshold, low_threshold, notifier):
        super().__init__()
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.running = True
        self.notifier = notifier
        self.last_high_notification = 0
        self.last_low_notification = 0
        self.notification_cooldown = 15

    def run(self):
        while self.running:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                charging = battery.power_plugged
                self.battery_status.emit(percent, charging)
                
                current_time = time.time()
                
                # Check for high battery (charging and above threshold)
                if (charging and percent >= self.high_threshold and 
                    current_time - self.last_high_notification > self.notification_cooldown):
                    self.notifier.send(
                        "Battery Alert 🔋",
                        f"Battery is at {percent}%. You should unplug the charger.",
                        True
                    )
                    self.last_high_notification = current_time
                
                # Check for low battery (not charging and at or below threshold)
                if (not charging and percent <= self.low_threshold and 
                    current_time - self.last_low_notification > self.notification_cooldown):
                    self.notifier.send(
                        "Low Battery Alert ⚠️",
                        f"Battery is at {percent}%. You should plug in the charger.",
                        True
                    )
                    self.last_low_notification = current_time

            # Responsive sleep: checks every second to allow faster shutdown
            for _ in range(30):
                if not self.running:
                    return
                time.sleep(1)

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

    def update_thresholds(self, new_high_threshold, new_low_threshold):
        self.high_threshold = new_high_threshold
        self.low_threshold = new_low_threshold
        print(f"Thresholds updated - High: {new_high_threshold}%, Low: {new_low_threshold}%")


class BatteryMonitorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.notifier = NotificationManager()
        self.monitor_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Battery Monitor')
        self.setGeometry(300, 300, 350, 250)

        layout = QVBoxLayout()

        # High threshold (unplug notification)
        self.high_threshold_label = QLabel('High Battery Threshold (%) - Unplug Charger:', self)
        layout.addWidget(self.high_threshold_label)

        self.high_threshold_input = QSpinBox(self)
        self.high_threshold_input.setRange(50, 100)
        self.high_threshold_input.setValue(60)
        layout.addWidget(self.high_threshold_input)

        # Low threshold (plug in notification)
        self.low_threshold_label = QLabel('Low Battery Threshold (%) - Plug Charger:', self)
        layout.addWidget(self.low_threshold_label)

        self.low_threshold_input = QSpinBox(self)
        self.low_threshold_input.setRange(1, 50)
        self.low_threshold_input.setValue(40)
        layout.addWidget(self.low_threshold_input)

        self.update_threshold_button = QPushButton('Update Thresholds', self)
        self.update_threshold_button.clicked.connect(self.applyThresholds)
        layout.addWidget(self.update_threshold_button)

        # Buttons layout
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton('Start Monitoring', self)
        self.start_button.clicked.connect(self.startMonitoring)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton('Stop Monitoring', self)
        self.stop_button.clicked.connect(self.stopMonitoring)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)

        # Test notification button
        self.test_button = QPushButton('Test Notification & Sound', self)
        self.test_button.clicked.connect(self.testNotification)
        layout.addWidget(self.test_button)

        # Status label
        self.status_label = QLabel('Status: Ready to start monitoring', self)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        self.tray_icon = QSystemTrayIcon(self)
        # Get the directory where your script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Create absolute path to the icon file
        icon_path = os.path.join(script_dir, "bat_icon.ico")

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
        high_threshold = self.high_threshold_input.value()
        low_threshold = self.low_threshold_input.value()
        
        if high_threshold <= low_threshold:
            self.status_label.setText('Error: High threshold must be greater than low threshold!')
            return
            
        self.monitor_thread = BatteryMonitor(high_threshold, low_threshold, self.notifier)
        self.monitor_thread.battery_status.connect(self.updateStatus)
        self.monitor_thread.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText('Status: Monitoring active')

    def stopMonitoring(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText('Status: Monitoring stopped')

    def applyThresholds(self):
        if self.monitor_thread:
            high_threshold = self.high_threshold_input.value()
            low_threshold = self.low_threshold_input.value()
            
            if high_threshold <= low_threshold:
                self.status_label.setText('Error: High threshold must be greater than low threshold!')
                return
                
            self.monitor_thread.update_thresholds(high_threshold, low_threshold)
            self.status_label.setText(f'Thresholds updated - High: {high_threshold}%, Low: {low_threshold}%')
        else:
            self.status_label.setText("Error: Monitoring not active. Start monitoring first.")

    def updateStatus(self, percent, charging):
        charge_status = "Charging" if charging else "Not Charging"
        self.status_label.setText(f'Status: {percent}% - {charge_status}')

    def testNotification(self):
        self.notifier.send(
            "Test Notification 🔔",
            "This is a test notification with sound!",
            True
        )

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