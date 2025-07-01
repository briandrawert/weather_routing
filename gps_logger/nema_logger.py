import serial
import pynmea2
import json
from datetime import datetime, timezone
import os
import numpy as np
from scipy.interpolate import interp2d

# === Polar file parsing ===
def parse_polar_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    tws_values = list(map(float, lines[0].strip().split(';')[1:]))
    twa_values = []
    speed_table = []
    for line in lines[1:]:
        parts = line.strip().split(';')
        twa_values.append(float(parts[0]))
        speed_table.append(list(map(float, parts[1:])))
    return np.array(twa_values), np.array(tws_values), np.array(speed_table)

def interpolate_polar_speed(twa, tws, twa_array, tws_array, speed_matrix):
    if not (twa_array[0] <= twa <= twa_array[-1]) or not (tws_array[0] <= tws <= tws_array[-1]):
        return None
    interp_func = interp2d(tws_array, twa_array, speed_matrix, kind='linear')
    return float(interp_func(tws, twa)[0])

# === Load polar data ===
twa_array, tws_array, speed_matrix = parse_polar_file("/home/brian/polars/Rhiannon-ORR.pol")

# === Serial port settings ===
ser = serial.Serial('/dev/ttyUSB0', 4800, timeout=1)

# === Data structure ===
latest_data = {
    "latitude": None,
    "longitude": None,
    "sog": None,
    "cog": None,
    "wind_speed": None,
    "wind_dir": None,
    "boat_speed": None,
    "heading": None,
    "twa": None,
    "tws": None,
    "percent_polars": None
}
last_log_minute = None

# === Paths ===
json_path = '/var/www/html/nmea_data.json'
log_dir = '/home/brian/nmea_logs'
os.makedirs(log_dir, exist_ok=True)

# === Main loop ===
while True:
    try:
        line = ser.readline().decode(errors='ignore').strip()
        if not line.startswith('$II'):
            continue
        print("RAW:", line)

        try:
            msg = pynmea2.parse(line)
        except Exception as e:
            print("Parse error:", e)
            continue

        if isinstance(msg, pynmea2.RMC):
            try:
                latest_data["latitude"] = msg.latitude
                latest_data["longitude"] = msg.longitude
                latest_data["sog"] = float(msg.spd_over_grnd)
                latest_data["cog"] = float(msg.true_course)
            except Exception as e:
                print("Error: RMC", e)

        elif msg.sentence_type == "MWV":
            try:
                if msg.reference == "R":  # Relative wind
                    latest_data["twa"] = float(msg.wind_angle)
                    latest_data["tws"] = float(msg.wind_speed)
                latest_data["wind_dir"] = float(msg.wind_angle)
                latest_data["wind_speed"] = float(msg.wind_speed)
            except Exception as e:
                print("Error: MWV", e)

        elif msg.sentence_type == "VHW":
            print("DEBUG: VHW fields:", vars(msg))
            try:
                if hasattr(msg, 'speed_knots') and msg.speed_knots:
                    latest_data["boat_speed"] = float(msg.speed_knots)
                if hasattr(msg, 'true_heading') and msg.true_heading:
                    latest_data["heading"] = float(msg.true_heading)
            except Exception as e:
                print("Error: VHW", e)

        # Compute percent of polars
        try:
            if latest_data["twa"] is not None and latest_data["tws"] is not None:
                actual_speed = latest_data["boat_speed"] if latest_data["boat_speed"] is not None else latest_data["sog"]
                target_speed = interpolate_polar_speed(
                    latest_data["twa"],
                    latest_data["tws"],
                    twa_array,
                    tws_array,
                    speed_matrix
                )
                if actual_speed is not None and target_speed is not None and target_speed > 0:
                    latest_data["percent_polars"] = round((actual_speed / target_speed) * 100, 1)
                else:
                    latest_data["percent_polars"] = None
        except Exception as e:
            print("Error computing % polars:", e)

        # === Write to JSON for frontend ===
        try:
            now = datetime.now(timezone.utc).isoformat()
            try:
                with open(json_path, 'r') as f:
                    current_data = json.load(f)
            except:
                current_data = {}

            for key in ["sog", "cog", "wind_speed", "wind_dir", "boat_speed", "heading", "percent_polars"]:
                if key not in current_data:
                    current_data[key] = []
                if latest_data[key] is not None:
                    current_data[key].append([now, latest_data[key]])
                    current_data[key] = current_data[key][-120:]

            with open(json_path, 'w') as f:
                json.dump(current_data, f)

        except Exception as e:
            print("Error writing JSON:", e)

        # === Write to log file once per minute ===
        current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
        if current_minute != last_log_minute:
            last_log_minute = current_minute
            log_filename = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
            with open(log_filename, 'a') as logf:
                log_line = f"{now} UTC," + ",".join([f"{k}:{latest_data[k]}" for k in latest_data]) + "\n"
                logf.write(log_line)
                print("Logged:", log_line.strip())

    except Exception as e:
        print("Main loop error:", e)

