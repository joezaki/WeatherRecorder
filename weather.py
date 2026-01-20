import serial
import csv
import time
import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QMessageBox, QFrame)
from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QFont


class ArduinoInterface(QThread):
    '''
    Class to interface directly with the Arduino to continuously
    extract BME280 data.
    '''
    data_received = Signal(list) 
    error_occurred = Signal(str)

    def __init__(self, port, baud):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=2)
            time.sleep(2) # let arduino reboot
        except Exception as e:
            self.error_occurred.emit(str(e))
            return

        while self.running:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    parts = line.split(',')
                    if len(parts) == 4:
                        # validate data is numeric before emitting
                        try:
                            # [status, temp, hum, pres]
                            clean_data = [parts[0], float(parts[1]), float(parts[2]), float(parts[3])]
                            self.data_received.emit(clean_data)
                        except ValueError:
                            bad_data = [parts[0], -1, -1, -1]
                            self.data_received.emit(bad_data)
            except Exception:
                pass
            time.sleep(0.01) # prevent CPU hogging

        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_command(self, command):
        if self.ser and self.ser.is_open:
            self.ser.write(command.encode())

    def stop(self):
        self.running = False
        self.wait()


class LinearGauge(QWidget):
    '''
    Custom widget that draws a 3-segment color bar
    and a position indicator pin.

    Parameters
    ==========
    config : dict
        Dictionary with keys ['low','high'] which dictate the color transitions
        from the middle bar to the low and high bars, respectively. And with keys
        ['min', 'max'] which dictate the low and high boundaries of the entire bar.
    colors : list
        List of 3 colors as hex strings, which indicate the low, middle, and high
        segments. Default is ["#FFEB3B","#4CAF50","#F44336"] which maps to ['yellow', 'green', 'red'].
    '''
    def __init__(
            self,
            config,
            colors=["#FFEB3B","#4CAF50","#F44336"]
            ):
        super().__init__()
        self.cfg = config
        self.value = self.cfg['min'] # start at min
        self.setMinimumHeight(30)
        self.setMinimumWidth(200)
        self.colors = colors

    def set_value(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # set ranges
        min_val = self.cfg['min']
        max_val = self.cfg['max']
        low_thresh = self.cfg['low']
        high_thresh = self.cfg['high']
        total_range = max_val - min_val

        # helper func to map value to pixels
        def val_to_px(v):
            if v < min_val: v = min_val
            if v > max_val: v = max_val
            return int((v - min_val) / total_range * w)

        x_low = val_to_px(low_thresh)
        x_high = val_to_px(high_thresh)

        # draw 3 zones
        painter.fillRect(0, 5, x_low, h-10, QColor(self.colors[0]))
        painter.fillRect(x_low, 5, x_high - x_low, h-10, QColor(self.colors[1]))
        painter.fillRect(x_high, 5, w - x_high, h-10, QColor(self.colors[2]))
        
        # set pin at current value
        pin_x = val_to_px(self.value)
        pen = QPen(QColor(0,0,0))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(pin_x, 0, pin_x, h)


class WeatherGUI(QMainWindow):
    '''
    The main GUI interface which displays the weather data and starts/stops
    recordings of the data to a specified directory.

    Parameters
    ==========
    recording_path : str
        Folder where data files should be stored.
    config : dict
        Dictionary indicating the ['label', 'unit', 'low', 'high', 'min', 'max']
        for each data type ('temp', 'hum', 'pres').
    serial_port : str
        Port that the Arduino of interest is set to. Default is 'COM3'.
    baud_rate : int
        The Arduino device communication speed. Make sure it matches what you have
        in the Arduino code (weather.ino). Default is 9600.
    colors : list
        List of 3 strings representing the hex colors of the 3 segments of the color gauges
        for the data streams. The 3 colors will be used for all 3 data streams. Default is
        ["#FFEB3B","#4CAF50","#F44336"] which maps to ['yellow', 'green', 'red'].
    '''
    def __init__(
            self,
            recording_path,
            config,
            serial_port='COM3',
            baud_rate=9600,
            colors=["#FFEB3B","#4CAF50","#F44336"]
            ):
        super().__init__()
        self.recording_path = recording_path
        self.config = config
        self.recording = False
        self.csv_file = None
        self.csv_writer = None
        
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.colors = colors
        
        if not os.path.exists(self.recording_path):
            os.makedirs(self.recording_path)

        self.setWindowTitle("Homecage Weather Sensor")
        self.resize(600, 450)
        self.setup_ui()
        
        self.worker = ArduinoInterface(self.serial_port, self.baud_rate)
        self.worker.data_received.connect(self.update_display)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.start()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # draw recording status
        self.status_label = QLabel("Not Recording")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(self.status_label)

        # add legend
        legend_text = QLabel()
        legend_text.setText((
            f"Legend: <span style='color: {self.colors[0]};'>Low </span>"
            f"<span style='color: {self.colors[1]};'>Normal </span>"
            f"<span style='color: {self.colors[2]};'>High </span>"
        ))
        legend_text.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(legend_text)

        # for each data, draw label, gauge, and value
        self.gauges = {}
        self.value_labels = {}
        for key in ['temp', 'hum', 'pres']:
            row_layout = QHBoxLayout()
            cfg = self.config[key]

            # add label
            lbl_name = QLabel(cfg['label'])
            lbl_name.setFixedWidth(100)
            
            # middle layout will have color gauge and min/max text
            middle_widget = QWidget()
            middle_layout = QVBoxLayout(middle_widget)
            middle_layout.setContentsMargins(0,5,0,5)
            middle_layout.setSpacing(0)

            # add color gauge
            gauge = LinearGauge(config=cfg, colors=self.colors)
            self.gauges[key] = gauge
            middle_layout.addWidget(gauge)

            # add min/max values as text
            labels_widget = QWidget()
            labels_layout = QHBoxLayout(labels_widget)
            labels_layout.setContentsMargins(0,0,0,0)

            min_lbl = QLabel(f"{cfg['min']}-")
            min_lbl.setAlignment(Qt.AlignLeft)
            min_lbl.setFont(QFont('Arial', 10))
            max_lbl = QLabel(f"{cfg['max']}+")
            max_lbl.setAlignment(Qt.AlignRight)
            max_lbl.setFont(QFont('Arial', 10))

            labels_layout.addWidget(min_lbl)
            labels_layout.addStretch()
            labels_layout.addWidget(max_lbl)
            middle_layout.addWidget(labels_widget)
            
            # add current value label
            lbl_val = QLabel(f"-- {cfg['unit']}")
            lbl_val.setFixedWidth(100)
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.value_labels[key] = lbl_val

            # add everything to main layout
            row_layout.addWidget(lbl_name)
            row_layout.addWidget(middle_widget)
            row_layout.addWidget(lbl_val)
            
            frame = QFrame()
            frame.setLayout(row_layout)
            frame.setFrameShape(QFrame.StyledPanel)
            main_layout.addWidget(frame)
        
        # draw timestamp
        self.lbl_time = QLabel("Time: --")
        self.lbl_time.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_time)

        # add buttons
        btn_layout = QHBoxLayout()
        self.record_btn = QPushButton("Record")
        self.stop_btn = QPushButton("Stop Recording")
        self.stop_btn.setEnabled(False)
        self.record_btn.clicked.connect(self.start_recording)
        self.stop_btn.clicked.connect(self.stop_recording)

        btn_layout.addWidget(self.record_btn)
        btn_layout.addWidget(self.stop_btn)
        main_layout.addLayout(btn_layout)

    @Slot(list)
    def update_display(self, data):
        # data are in format [status, temp, hum, pres]
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        self.lbl_time.setText(f'Time: {current_time}')
        values = {'temp': data[1], 'hum': data[2], 'pres': data[3]}

        # update values on display
        for key, val in values.items():
            self.gauges[key].set_value(val)
            unit = self.config[key]['unit']
            self.value_labels[key].setText(f"{val:.2f} {unit}")

        # save if recording
        if self.recording and self.csv_writer:
            self.csv_writer.writerow([current_time, data[1], data[2], data[3]])

    def start_recording(self):
        filename = f"{time.strftime('%Y%m%d_%H%M%S')}_weather.csv"
        filepath = os.path.join(self.recording_path, filename)
        if not os.path.exists(os.path.dirname(filepath)):
            os.make_dirs(os.path.dirname(filepath))
        
        try:
            self.csv_file = open(filepath, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["Timestamp", "Temperature_C", "Humidity_Pct", "Pressure_hPa"])
        except Exception as e:
            self.show_error(f"Could not create file: {e}")
            return

        self.worker.send_command('1')
        self.recording = True
        self.status_label.setText(f"Recording to: {filename}")
        self.status_label.setStyleSheet("color: red;")
        self.btn_record.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_recording(self):
        self.worker.send_command('0')
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None

        self.recording = False
        self.status_label.setText("Not Recording")
        self.status_label.setStyleSheet("color: white;")
        self.btn_record.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        self.worker.stop()
        if self.csv_file:
            self.csv_file.close()
        event.accept()