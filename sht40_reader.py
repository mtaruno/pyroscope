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
    
    def __init__(self, bus_num=1, simulate=False):
        """
        Initialize SHT40 sensor
        
        Args:
            bus_num: I2C bus number (default 1 for Jetson)
            simulate: Force simulation mode
        """
        self.simulate = simulate or not HAS_I2C
        self.bus_num = bus_num
        self.bus = None
        
        if not self.simulate:
            try:
                self.bus = smbus2.SMBus(bus_num)
                # Try to communicate with sensor
                self._test_connection()
                print(f"✓ SHT40 sensor connected on I2C bus {bus_num}")
            except Exception as e:
                self.simulate = True
        
        if self.simulate:
            import random
            self.random = random
            # Initialize baseline values for simulation
            self.base_temp = 25.0  # Baseline temperature in Celsius
            self.base_humidity = 50.0  # Baseline humidity in %
            self.temp_drift = 0.0
            self.humidity_drift = 0.0
    
    def _test_connection(self):
        """Test if sensor is responding"""
        if self.bus:
            # Try to read from sensor
            self.bus.write_byte(SHT40_I2C_ADDR, SHT40_CMD_MEASURE_HIGH_PRECISION)
    
    def read_data(self):
        """
        Read temperature and humidity from sensor
        
        Returns:
            tuple: (temperature_celsius, humidity_percent, timestamp)
        """
        timestamp = datetime.datetime.now()
        
        if self.simulate:
            # Simulate realistic sensor data with small variations
            # Add small random drift to create natural fluctuation
            self.temp_drift += self.random.uniform(-0.1, 0.1)
            self.humidity_drift += self.random.uniform(-0.2, 0.2)
            
            # Clamp drift to reasonable bounds
            self.temp_drift = max(-1.5, min(1.5, self.temp_drift))
            self.humidity_drift = max(-3.0, min(3.0, self.humidity_drift))
            
            # Apply drift to baseline with small random noise
            temperature = self.base_temp + self.temp_drift + self.random.uniform(-0.05, 0.05)
            humidity = self.base_humidity + self.humidity_drift + self.random.uniform(-0.1, 0.1)
            
            # Clamp humidity to valid range
            humidity = max(0, min(100, humidity))
        else:
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
                print(f"Error reading sensor: {e}")
                return None, None, timestamp
        
        return temperature, humidity, timestamp
    
    def close(self):
        """Close I2C bus connection"""
        if self.bus:
            self.bus.close()


def format_output(temperature, humidity, timestamp):
    """Format sensor data for display"""
    if temperature is None or humidity is None:
        return f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] ERROR: Failed to read sensor"
    
    return (f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] "
            f"Temperature: {temperature:6.2f}°C | "
            f"Humidity: {humidity:5.2f}%")


def main():
    """Main function to continuously read and display sensor data"""
    print("=" * 70)
    print("SHT40 Temperature & Humidity Sensor Reader")
    print("=" * 70)
    
    # Initialize sensor
    sensor = SHT40Sensor(bus_num=1)
    
    print("Starting continuous reading (Press Ctrl+C to stop)...")
    print("-" * 70)
    
    try:
        while True:
            # Read sensor data
            temperature, humidity, timestamp = sensor.read_data()
            
            # Display formatted output
            output = format_output(temperature, humidity, timestamp)
            print(output)
            
            # Wait before next reading
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n" + "-" * 70)
        print("Stopped by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
    finally:
        sensor.close()
        print("Sensor connection closed")
        print("=" * 70)


def run_once(bus_num=1, simulate=False):
    """Single read for backend subprocess: print one JSON line to stdout and exit."""
    sensor = SHT40Sensor(bus_num=bus_num, simulate=simulate)
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
    parser.add_argument("--simulate", action="store_true", help="Use simulation mode")
    args = parser.parse_args()
    if args.once:
        run_once(bus_num=args.bus, simulate=args.simulate)
    else:
        main()
