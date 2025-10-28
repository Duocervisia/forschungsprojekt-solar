import time

"""Minimal main.py for ESP32: periodically read INA226 and print readings.

Assumptions:
- Uses `ina226.py` in the same directory (driver defines class INA226).
- Default I2C pins: SDA=21, SCL=22 (common on many ESP32 boards). Change below if needed.
- Default I2C address: 0x40 (INA226 default).
- Default read interval: 2 seconds (change INTERVAL_SECONDS).

This file is MicroPython-friendly and prints readings to the serial REPL.
"""

import time
from machine import I2C, Pin
from ina226 import INA226

# --- Configuration (edit if your board uses different pins or address) ---
SDA_PIN = 21
SCL_PIN = 22
I2C_FREQ = 100000
INA_ADDR = 0x40
INTERVAL_SECONDS = 2
SHUNT_MICRO_AMPERE_CORRECTION = -10 # MicroAmperes to add to current readings (e.g., for calibration)


def init_i2c(sda_pin=SDA_PIN, scl_pin=SCL_PIN, freq=I2C_FREQ):
    # On ESP32, id=0 or id=1 may be used depending on board; using default constructor
    try:
        i2c = I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
    except Exception:
        # Fallback if the board expects different constructor signature
        i2c = I2C(scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
    return i2c


def main():
    print("Starting INA226 reader")
    print("I2C SDA={}, SCL={}, addr=0x{:02x}, interval={}s".format(SDA_PIN, SCL_PIN, INA_ADDR, INTERVAL_SECONDS))

    i2c = init_i2c()

    # Create the driver instance. The INA226 class in `ina226.py` expects an object
    # with readfrom_mem_into and writeto_mem (MicroPython's machine.I2C provides these).
    try:
        ina = INA226(i2c, addr=INA_ADDR)
    except Exception as exc:
        print("Failed to initialize INA226:", exc)
        return

    # Use a 10 ohm shunt resistor: configure calibration accordingly.
    # This library's `calibrate` expects r_shunt in mOhm (so 10 Ohm -> 10000).
    try:
        ina.calibrate(r_shunt=10000)
    except Exception as exc:
        print("Warning: failed to set custom calibration:", exc)

    while True:
        try:
            # Driver returns shunt voltage in mV; convert to Volts for printing
            shunt_v = ina.shunt_voltage / 1000.0
            bus_v = ina.bus_voltage        # Volts
            current = ina.current + SHUNT_MICRO_AMPERE_CORRECTION / 1000000.0  # current returned in Amps
            power = ina.power              # Watts

            # Convert to mA for friendly logging (matches previous behavior)
            current_mA = current * 1000.0

            # Print a compact CSV-like line for logging/parsing
            print("shunt_v={:.6f}V,bus_v={:.3f}V,current={:.6f}mA,power={:.6f}W".format(
                shunt_v, bus_v, current_mA, power
            ))

        except Exception as e:
            print("Error reading INA226:", e)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()