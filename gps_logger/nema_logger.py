import serial
import pynmea2
import time
from datetime import datetime, timezone

SERIAL_PORT = '/dev/ttyUSB0'   # Update this as needed
BAUD_RATE = 4800               # Standard NMEA baud rate

def collect_nmea_data(serial_conn, duration=60):
    """Collects NMEA data for a duration and returns the most recent values."""
    data = {
        'latitude': None,
        'longitude': None,
        'sog': None,         # Speed over ground
        'cog': None,         # Course over ground
        'wind_dir': None,
        'wind_speed': None,
        'boat_speed': None,  # Speed through water
    }

    start_time = time.time()

    while time.time() - start_time < duration:
        try:
            line = serial_conn.readline().decode('ascii', errors='replace').strip()

            if not line.startswith('$II') and not line.startswith('$GP'):
                continue

            if line.startswith('$IIRMC'):
                try:
                    msg = pynmea2.parse(line)
                    data['latitude'] = getattr(msg, 'latitude', None)
                    data['longitude'] = getattr(msg, 'longitude', None)
                    data['sog'] = getattr(msg, 'spd_over_grnd', None)
                    data['cog'] = getattr(msg, 'true_course', None)
                except pynmea2.nmea.ParseError:
                    continue

            elif line.startswith('$IIMWV'):
                try:
                    msg = pynmea2.parse(line)
                    if msg.status == 'A':
                        data['wind_dir'] = msg.wind_angle
                        data['wind_speed'] = msg.wind_speed
                except pynmea2.nmea.ParseError:
                    continue

            elif line.startswith('$IIVHW'):
                try:
                    fields = line.split(',')
                    if len(fields) >= 7 and fields[5]:
                        data['boat_speed'] = float(fields[5])
                except (ValueError, IndexError):
                    continue


            #return if we have collected all the data
            if not any(v is None for v in data.values()):
                return data
 
        except Exception as e:
            print(f"Error: {e}")
            continue

    return data

def log_gps():
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
        while True:
            values = collect_nmea_data(ser)
            now = datetime.now(timezone.utc)
            log_filename = now.strftime("%Y-%m-%d") + ".log"

            log_entry = f"{now.isoformat()} UTC, "
            log_entry += f"Lat: {values['latitude']}, Lon: {values['longitude']}, "
            log_entry += f"SOG: {values['sog']} kn, COG: {values['cog']}°, "
            log_entry += f"Wind: {values['wind_dir']}° at {values['wind_speed']} kn, "
            log_entry += f"Boat Speed: {values['boat_speed']} kn "

            with open(log_filename, "a") as logfile:
                logfile.write(log_entry)
                logfile.write("\n")

            print(f"Logged: {log_entry.strip()}")
            time.sleep(60)

if __name__ == "__main__":
    log_gps()

