import sys
from PySide6.QtWidgets import QApplication
import weather

# --- CONFIGURATION ---
serial_port = 'COM3'  # update this to your Arduino port
baud_rate = 9600
recording_path = "./data/weather/"

# define config values
# low/high reflect beginning of yellow/red zones, respectively
# min/max reflect lower/upper ends of the display bar range
sensor_config = {
    'temp': {
	    'label': 'Temperature',
	    'unit' : '°C',
	    'low'  : 20.0,
	    'high' : 26.0,
	    'min'  : 10.0,
	    'max'  : 35.0
	    },
    'hum': {
	    'label': 'Humidity',
	    'unit' : '%',
	    'low'  : 30.0,
	    'high' : 60.0,
	    'min'  : 0.0,
	    'max'  : 100.0
	    },
    'pres': {
	    'label': 'Pressure',
	    'unit' : 'hPa',
	    'low'  : 1000.0,
	    'high' : 1020.0,
	    'min'  : 980.0,
	    'max'  : 1040.0
	    }
}

# run GUI
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = weather.WeatherGUI(
        recording_path=recording_path,
        config=sensor_config,
        serial_port=serial_port,
        baud_rate=baud_rate
        )
    window.show()
    sys.exit(app.exec())