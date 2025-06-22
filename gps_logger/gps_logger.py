import serial
import pynmea2
import time
from datetime import datetime, timezone


# Configure your serial port here
SERIAL_PORT = '/dev/ttyUSB0'  # Change to your actual port
BAUD_RATE = 4800  # Typical for NMEA 0183

def get_gps_data(serial_conn):
    while True:
        try:
            line = serial_conn.readline().decode('ascii', errors='replace')
            print(f"RAW: {line}")  # <-- Debug line
            if line.startswith('$GPGGA') or line.startswith('$GPRMC') or line.startswith('$IIRMC'):
                msg = pynmea2.parse(line)
                if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                    return (msg.latitude, msg.longitude)
        except pynmea2.nmea.ParseError:
            continue
        except Exception as e:
            print(f"Error: {e}")
            break
    return (None, None)

def log_gps():
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
        while True:
            lat, lon = get_gps_data(ser)
            print(f"GPS: {lat}, {lon}")
            if lat is not None and lon is not None:
                now = datetime.now(timezone.utc)
                log_filename = now.strftime("%Y-%m-%d") + ".log"
                log_entry = f"{now.isoformat()} UTC, Lat: {lat:.6f}, Lon: {lon:.6f}\n"

                with open(log_filename, "a") as logfile:
                    logfile.write(log_entry)
                print(f"Logged: {log_entry.strip()}")
            time.sleep(60)

if __name__ == "__main__":
    log_gps()

