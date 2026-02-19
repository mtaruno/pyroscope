#!/usr/bin/env python3
"""
SHT40 Temperature and Humidity Sensor Reader for Jetson
Reads data from SHT40 sensor via I2C and outputs with timestamp
"""

import argparse
import json
import time
import datetime
import sys

# Try to import real I2C library
try:
    import smbus2
    HAS_I2C = True
except ImportError:
    HAS_I2C = False

# SHT40 I2C address and commands
SHT40_I2C_ADDR = 0x44
SHT40_CMD_MEASURE_HIGH_PRECISION = 0xFD


class SHT40Sensor:
    """SHT40 Temperature and Humidity Sensor Interface"""

    def __init__(self, bus_num=1):
        """
        Initialize SHT40 sensor.

        Args:
            bus_num: I2C bus number (default 1 for Jetson)
        """
        if not HAS_I2C:
            raise RuntimeError("smbus2 not installed. Install with: pip install smbus2")
        self.bus_num = bus_num
        self.bus = smbus2.SMBus(bus_num)
        self._test_connection()
        print(f"SHT40 sensor connected on I2C bus {bus_num}")

    def _test_connection(self):
        """Test if sensor is responding."""
        self.bus.write_byte(SHT40_I2C_ADDR, SHT40_CMD_MEASURE_HIGH_PRECISION)

    def read_data(self):
        """
        Read temperature and humidity from sensor.

        Returns:
            tuple: (temperature_celsius, humidity_percent, timestamp)
        """
        timestamp = datetime.datetime.now()
        try:
            # Send measurement command
            self.bus.write_byte(SHT40_I2C_ADDR, SHT40_CMD_MEASURE_HIGH_PRECISION)

            # Wait for measurement to complete (typical 8.2ms for high precision)
            time.sleep(0.01)

            # Read 6 bytes: temp MSB, temp LSB, temp CRC, hum MSB, hum LSB, hum CRC
            data = self.bus.read_i2c_block_data(SHT40_I2C_ADDR, 0x00, 6)

            # Convert temperature (formula from datasheet)
            temp_raw = (data[0] << 8) | data[1]
            temperature = -45 + 175 * (temp_raw / 65535.0)

            # Convert humidity (formula from datasheet)
            hum_raw = (data[3] << 8) | data[4]
            humidity = -6 + 125 * (hum_raw / 65535.0)

            # Clamp humidity to valid range
            humidity = max(0, min(100, humidity))

        except Exception as e:
            print(f"Error reading sensor: {e}", file=sys.stderr)
            return None, None, timestamp

        return temperature, humidity, timestamp

    def close(self):
        """Close I2C bus connection."""
        if self.bus:
            self.bus.close()


def format_output(temperature, humidity, timestamp):
    """Format sensor data for display."""
    if temperature is None or humidity is None:
        return f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] ERROR: Failed to read sensor"

    return (f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] "
            f"Temperature: {temperature:6.2f}C | "
            f"Humidity: {humidity:5.2f}%")


def main():
    """Main function to continuously read and display sensor data."""
    print("=" * 70)
    print("SHT40 Temperature & Humidity Sensor Reader")
    print("=" * 70)

    try:
        sensor = SHT40Sensor(bus_num=1)
    except Exception as e:
        print(f"Cannot open SHT40: {e}", file=sys.stderr)
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
        print("Sensor connection closed")
        print("=" * 70)


def run_once(bus_num=1):
    """Single read for backend subprocess: print one JSON line to stdout and exit."""
    try:
        sensor = SHT40Sensor(bus_num=bus_num)
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
    parser = argparse.ArgumentParser(description="SHT40 Temperature & Humidity Reader")
    parser.add_argument("--once", action="store_true", help="Single read, output JSON to stdout and exit")
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (default 1)")
    args = parser.parse_args()
    if args.once:
        run_once(bus_num=args.bus)
    else:
        main()
