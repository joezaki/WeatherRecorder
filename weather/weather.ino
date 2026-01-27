#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

#define SYNC_PIN 2
Adafruit_BME280 bme; 

bool isRecording = false;
int msBetweenReadings = 1000; // ms delay between readings

void setup() {
  Serial.begin(9600);
  pinMode(SYNC_PIN, OUTPUT);
  digitalWrite(SYNC_PIN, LOW);

  // generic BME280 sensors us 0x76
  if (!bme.begin(0x77)) {
    Serial.println("Error: BME280 sensor not found.");
    while (1);
  }
}

void loop() {
  // start recording when signal is sent
  if (Serial.available() > 0) {
    char command = Serial.read();
    if (command == '1') {
      isRecording = true;
    } else if (command == '0') {
      isRecording = false;
    }
  }

  // send TTL if recording
  if (isRecording) {
    digitalWrite(SYNC_PIN, HIGH);
  }

  // read data
  float temp = bme.readTemperature();
  float hum = bme.readHumidity();
  float pres = bme.readPressure() / 100.0F;
  
  // turn off TTL if recording
  if (isRecording) {
	  delay(10); // test if ephys I/O board can read the pulse without this delay, if so, remove this and delay below
	  digitalWrite(SYNC_PIN, LOW);
	}

  // send data
  Serial.print(isRecording); 
  Serial.print(",");
  Serial.print(temp);
  Serial.print(",");
  Serial.print(hum);
  Serial.print(",");
  Serial.println(pres);

  // delay until next reading
  // note delay is 10ms less for first reading because of delay() above
  if (isRecording) {
    delay(msBetweenReadings-10); 
  } else {
    delay(msBetweenReadings);
  }
}