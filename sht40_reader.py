#!/usr/bin/env python3
"""
SHT40 Temperature and Humidity Sensor Reader (Arduino Nano over Serial).
Hardware: SHT40 -> Arduino Nano (I2C) -> USB -> Jetson/PC.

Arduino sketch must send one line per reading: "temperature,humidity"
  e.g. Serial.println((String)temp + "," + (String)hum);
  Use 9600 baud (Serial.begin(9600)) unless you pass --baud.
"""

import argparse
import json
import time
import datetime
import sys

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# Stable by-id path so port name does not change (ttyUSB0 vs ttyUSB1). Use same Arduino each time.
DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
DEFAULT_BAUD = 9600
# Timeout for reading one line (seconds)
READ_TIMEOUT = 2.0


class SHT40Sensor:
    """SHT40 via Arduino Nano over serial. One line per read: 'temp,hum'."""

    def __init__(self, port=None, baud=9600):
        """
        Open serial connection to Arduino.

        Args:
            port: Serial port (e.g. /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 on Linux, COM3 on Windows).
            baud: Baud rate (default 9600). Must match Arduino Serial.begin().
        """
        if not HAS_SERIAL:
            raise RuntimeError("pyserial not installed. Install with: pip install pyserial")
        self.port = port or DEFAULT_PORT
        self.baud = int(baud)
        self.ser = serial.Serial(self.port, self.baud, timeout=READ_TIMEOUT)
        # Allow Arduino to reset on connect (DTR); brief delay for boot
        time.sleep(0.5)
        self.ser.reset_input_buffer()
        print(f"SHT40 (Arduino) connected on {self.port} @ {self.baud} baud")

    def read_data(self):
        """
        Read one line from Arduino and parse "temperature,humidity".

        Returns:
            tuple: (temperature_celsius, humidity_percent, timestamp)
        """
        timestamp = datetime.datetime.now()
        try:
            line = self.ser.readline()
            if not line:
                return None, None, timestamp
            line = line.decode("utf-8", errors="ignore").strip()
            if not line:
                return None, None, timestamp
            parts = line.split(",")
            if len(parts) < 2:
                return None, None, timestamp
            temperature = float(parts[0].strip())
            humidity = float(parts[1].strip())
            humidity = max(0, min(100, humidity))
        except (ValueError, UnicodeDecodeError) as e:
            print(f"Parse error: {e} (line: {line!r})", file=sys.stderr)
            return None, None, timestamp
        except Exception as e:
            print(f"Error reading serial: {e}", file=sys.stderr)
            return None, None, timestamp
        return temperature, humidity, timestamp

    def close(self):
        """Close serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()


def format_output(temperature, humidity, timestamp):
    """Format sensor data for display."""
    if temperature is None or humidity is None:
        return f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] ERROR: Failed to read sensor"

    return (f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] "
            f"Temperature: {temperature:6.2f}C | "
            f"Humidity: {humidity:5.2f}%")


def main(port=None, baud=9600):
    """Continuous read and display."""
    print("=" * 70)
    print("SHT40 (Arduino Serial) Temperature & Humidity Reader")
    print("=" * 70)

    try:
        sensor = SHT40Sensor(port=port or DEFAULT_PORT, baud=baud)
    except Exception as e:
        print(f"Cannot open serial: {e}", file=sys.stderr)
        sys.exit(1)

    print("Starting continuous reading (Press Ctrl+C to stop)...")
    print("-" * 70)

    try:
        while True:
            temperature, humidity, timestamp = sensor.read_data()
            output = format_output(temperature, humidity, timestamp)
            print(output)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n" + "-" * 70)
        print("Stopped by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        sensor.close()
        print("Serial connection closed")
        print("=" * 70)


def run_once(port=None, baud=9600):
    """Single read: print one JSON line to stdout and exit. Used by backend subprocess."""
    try:
        sensor = SHT40Sensor(port=port or DEFAULT_PORT, baud=baud)
    except Exception as e:
        print(json.dumps({"temperature": None, "humidity": None, "timestamp": None, "error": str(e)}))
        return
    try:
        temperature, humidity, timestamp = sensor.read_data()
        ts = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        out = {
            "temperature": round(temperature, 2) if temperature is not None else None,
            "humidity": round(humidity, 2) if humidity is not None else None,
            "timestamp": ts,
        }
        print(json.dumps(out))
    finally:
        sensor.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SHT40 via Arduino Nano (serial). Expects lines: temperature,humidity"
    )
    parser.add_argument("--once", action="store_true", help="Single read, output JSON to stdout and exit")
    parser.add_argument("--port", type=str, default=DEFAULT_PORT, help=f"Serial port (default {DEFAULT_PORT})")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate (default {DEFAULT_BAUD})")
    args = parser.parse_args()

    if args.once:
        run_once(port=args.port, baud=args.baud)
    else:
        main(port=args.port, baud=args.baud)
