# The MIT License (MIT)
#
# Copyright (c) 2017 Dean Miller for Adafruit Industries
# Copyright (c) 2020 Christian Becker
# Copyright (c) 2025 Andrey Tarasov
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
`ina226`
====================================================

Micropython driver for the INA226 current sensor.

* Author(s): Andrey Tarasov

"""

# Forked from https://github.com/elschopi/TI_INA226_micropython


from micropython import const

__version__ = "1.1.0"
__repo__ = "https://github.com/ankcn/TI_INA226_micropython.git"


# Register definitions

# Config Register (R/W)
_REG_CONFIG = const(0x00)

# Shunt voltage register (R)
_REG_SHUNTVOLTAGE = const(0x01)

# Bus voltage register (R)
_REG_BUSVOLTAGE = const(0x02)

# Power register (R)
_REG_POWER = const(0x03)

# Current register (R)
_REG_CURRENT = const(0x04)

# Calibration register (R/W)
_REG_CALIBRATION = const(0x05)


# Configuration register values

# Reset Bit
CONFIG_RESET = const(0x8000)

# Constant bits - don't change
CONFIG_CONST_BITS = const(0x4000)

# Averaging modes
CONFIG_AVGMODE_MASK = const(0x0e00)
CONFIG_AVGMODE_1SAMPLES = const(0x0000)
CONFIG_AVGMODE_4SAMPLES = const(0x0200)
CONFIG_AVGMODE_16SAMPLES = const(0x0400)
CONFIG_AVGMODE_64SAMPLES = const(0x0600)
CONFIG_AVGMODE_128SAMPLES = const(0x0800)
CONFIG_AVGMODE_256SAMPLES = const(0x0a00)
CONFIG_AVGMODE_512SAMPLES = const(0x0c00)
CONFIG_AVGMODE_1024SAMPLES = const(0x0e00)

# Bus voltage conversion times
CONFIG_VBUSCT_MASK = const(0x01c0)
CONFIG_VBUSCT_140us = const(0x0000)
CONFIG_VBUSCT_204us = const(0x0040)
CONFIG_VBUSCT_332us = const(0x0080)
CONFIG_VBUSCT_588us = const(0x00c0)
CONFIG_VBUSCT_1100us = const(0x0100)
CONFIG_VBUSCT_2116us = const(0x0140)
CONFIG_VBUSCT_4156us = const(0x0180)
CONFIG_VBUSCT_8244us = const(0x01c0)

# Shunt voltage conversion times
CONFIG_VSHUNTCT_MASK = const(0x0038)
CONFIG_VSHUNTCT_140us = const(0x0000)
CONFIG_VSHUNTCT_204us = const(0x0008)
CONFIG_VSHUNTCT_332us = const(0x0010)
CONFIG_VSHUNTCT_588us = const(0x0018)
CONFIG_VSHUNTCT_1100us = const(0x0020)
CONFIG_VSHUNTCT_2116us = const(0x0028)
CONFIG_VSHUNTCT_4156us = const(0x0030)
CONFIG_VSHUNTCT_8244us = const(0x0038)

# Operating modes
CONFIG_MODE_MASK = const(0x0007)  # Operating Mode Mask
CONFIG_MODE_POWERDOWN = const(0x0000)
CONFIG_MODE_SVOLT_TRIGGERED = const(0x0001)
CONFIG_MODE_BVOLT_TRIGGERED = const(0x0002)
CONFIG_MODE_SANDBVOLT_TRIGGERED = const(0x0003)
CONFIG_MODE_ADCOFF = const(0x0004)
CONFIG_MODE_SVOLT_CONTINUOUS = const(0x0005)
CONFIG_MODE_BVOLT_CONTINUOUS = const(0x0006)
CONFIG_MODE_SANDBVOLT_CONTINUOUS = const(0x0007)

# Default configuration register value
_DEF_CONFIG = const(CONFIG_CONST_BITS |
    CONFIG_AVGMODE_512SAMPLES |
    CONFIG_VBUSCT_588us |
    CONFIG_VSHUNTCT_588us |
    CONFIG_MODE_SANDBVOLT_CONTINUOUS)


def _to_signed(num):
    if num > 0x7FFF:
        num -= 0x10000
    return num


class INA226:
    """Driver for the INA226 current sensor"""
    def __init__(self, i2c_device, addr=0x40):
        self.i2c_device = i2c_device

        self.i2c_addr = addr
        self.buf = bytearray(2)
        # Multiplier in mA used to determine current from raw reading
        self._current_lsb = 0
        # Multiplier in W used to determine power from raw reading
        self._power_lsb = 0

        # Set chip to known config values to start
        self.calibrate()

    def _write_register(self, reg, value):
        self.buf[0] = (value >> 8) & 0xFF
        self.buf[1] = value & 0xFF
        self.i2c_device.writeto_mem(self.i2c_addr, reg, self.buf)

    def _read_register(self, reg):
        self.i2c_device.readfrom_mem_into(self.i2c_addr, reg & 0xff, self.buf)
        value = (self.buf[0] << 8) | (self.buf[1])
        return value

    @property
    def shunt_voltage(self):
        """The shunt voltage (between IN+ and IN-) in mVolts (so +-81.92mV)"""
        value = _to_signed(self._read_register(_REG_SHUNTVOLTAGE))
        # The least signficant bit is 2.5uV or 0.0025 mV
        return value * 0.0025

    @property
    def bus_voltage(self):
        """The bus voltage (between Vbus and GND) in Volts"""
        # Voltage in mV is register content multiplied with 1.25mV/bit
        # Return Volts instead of milliVolts
        return self._read_register(_REG_BUSVOLTAGE) * 1.25 / 1000

    @property
    def current(self):
        """The current through the shunt resistor in milliamps."""
        # Sometimes a sharp load will reset the INA219, which will
        # reset the cal register, meaning CURRENT and POWER will
        # not be available ... athis by always setting a cal
        # value even if it's an unfortunate extra step
        self._write_register(_REG_CALIBRATION, self._cal_value)

        # Now we can safely read the CURRENT register!
        raw_current = _to_signed(self._read_register(_REG_CURRENT))
        return raw_current * self._current_lsb

    @property
    def power(self):
        # INA226 stores the calculated power in this register
        raw_power = _to_signed(self._read_register(_REG_POWER))
        # Calculated power is derived by multiplying raw power value with the power LSB
        return raw_power * self._power_lsb

    def calibrate(self, config=_DEF_CONFIG, max_current=None, v_shunt=75.0, r_shunt=100.0):
        """
        Set up the INA226 by writing calibration and configuration values
        to appropriate registers. The calibration value is calculated based
        on the maximum expected current and the corresponding voltage drop
        across the shunt resistor. Instead of the maximum current,
        you can specify the shunt resistance.
        Args:
            config (int): Configuration register value
            max_current (float): Maximum expected current (A)
            v_shunt (float): Nominal shunt drop voltage at maximum current (mV)
            r_shunt (float): Nominal shunt resistance (mOhm)
        """
        if max_current == None:
            max_current = v_shunt / r_shunt
        self._cal_value = int(5.12 * (1 << 15) / v_shunt)
        self._current_lsb = max_current / (1 << 15)
        self._power_lsb = 25 * self._current_lsb
        self._write_register(_REG_CALIBRATION, self._cal_value)
        self._write_register(_REG_CONFIG, config)