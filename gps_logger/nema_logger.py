import serial
import pynmea2
import time
import json
import os
from datetime import datetime, timezone
from collections import deque

# === Configuration ===
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 4800
PHP_JSON_PATH = '/var/www/html/nmea_data.json'
LOG_DIR = '/home/brian/gps_logger/logs'
VARIABLES = ['latitude', 'longitude', 'sog', 'cog', 'wind_speed', 'wind_dir', 'boat_speed', 'heading']
BUFFER_SECONDS = 600

os.makedirs(LOG_DIR, exist_ok=True)
data_buffer = {var: deque(maxlen=BUFFER_SECONDS) for var in VARIABLES}
last_log_minute = None
latest_values = {var: None for var in VARIABLES}

# === NMEA Parsing ===
def parse_nmea_sentence(sentence):
    parsed = {}
    try:
        msg = pynmea2.parse(sentence)

        if isinstance(msg, pynmea2.types.talker.RMC):
            if msg.status == 'A':
                parsed['latitude'] = msg.latitude
                parsed['longitude'] = msg.longitude
                parsed['sog'] = float(msg.spd_over_grnd or 0.0)
                parsed['cog'] = float(msg.true_course or 0.0)

        elif msg.sentence_type == 'MWV' and msg.status == 'A':
            parsed['wind_dir'] = float(msg.wind_angle or 0.0)
            parsed['wind_speed'] = float(msg.wind_speed or 0.0)

        elif msg.sentence_type == 'VHW':
            parsed['boat_speed'] = float(msg.speed_knots or 0.0)

        elif msg.sentence_type == 'HDG':
            parsed['heading'] = float(msg.heading or 0.0)

    except pynmea2.ParseError:
        pass

    return parsed

# === Logging and Streaming ===
def write_minute_log(timestamp, data):
    date_str = timestamp.strftime('%Y-%m-%d')
    log_path = os.path.join(LOG_DIR, f'{date_str}.log')
    with open(log_path, 'a') as f:
        line = f"{timestamp.isoformat()} UTC," + ",".join(f"{k}:{data.get(k)}" for k in VARIABLES) + "\n"
        f.write(line)

def update_php_json():
    output = {var: list(data_buffer[var]) for var in VARIABLES}
    try:
        with open(PHP_JSON_PATH, 'w') as f:
            json.dump(output, f)
    except Exception as e:
        print(f"Failed to write JSON: {e}")

# === Main Loop ===
def main():
    global last_log_minute
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
        while True:
            try:
                line = ser.readline().decode('ascii', errors='replace').strip()
                parsed = parse_nmea_sentence(line)

                if not parsed:
                    continue

                timestamp = datetime.now(timezone.utc)

                # Update current values and buffer
                for var in VARIABLES:
                    val = parsed.get(var)
                    if val is not None:
                        latest_values[var] = val
                        data_buffer[var].append((timestamp.isoformat(), val))

                # Update frontend JSON every second
                update_php_json()

                # Write to log once per minute
                current_minute = timestamp.strftime('%Y-%m-%d %H:%M')
                if current_minute != last_log_minute:
                    write_minute_log(timestamp, latest_values)
                    last_log_minute = current_minute

                time.sleep(1)

            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)

if __name__ == '__main__':
    main()

