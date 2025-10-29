
import time
from machine import I2C, Pin
from lib.ina226 import INA226

try:
	import config
except Exception:
	config = None

"""CurrentReader

Wrapper class around INA226 reading and I2C initialization.

Usage example (on the ESP32 REPL):

	from current_reader import CurrentReader
	r = CurrentReader()
	r.run()  # blocking loop printing measurements

The class also exposes `read()` which returns a dict with current readings
so it can be unit-tested or called from another scheduler.
"""


class CurrentReader:
	def __init__(
		self,
		sda_pin=None,
		scl_pin=None,
		i2c_freq=None,
		ina_addr=None,
		interval_seconds=None,
		shunt_microampere_correction=None,
		r_shunt_mohm=None,
		i2c=None,
	):
		"""Initialize reader.

		Parameters:
			sda_pin, scl_pin, i2c_freq: I2C bus pins and frequency.
			ina_addr: I2C address of the INA226.
			interval_seconds: sleep between measurements in `run()`.
			shunt_microampere_correction: microamp correction applied to current.
			r_shunt_mohm: shunt resistance in mOhm used for calibration (or None).
			i2c: optional pre-created I2C instance (useful for testing).
		"""

		self.sda_pin = sda_pin
		self.scl_pin = scl_pin
		self.i2c_freq = i2c_freq
		self.ina_addr = ina_addr

		# Load defaults from config.ina226 when available, otherwise fall back
		# to the original hard-coded defaults.
		cfg = getattr(config, 'ina226', {}) if config else {}

		self.interval_seconds = interval_seconds if interval_seconds is not None else cfg.get('interval_seconds', 2)
		self.shunt_microampere_correction = (
			shunt_microampere_correction
			if shunt_microampere_correction is not None
			else cfg.get('shunt_microampere_correction', -10)
		)
		self.r_shunt_mohm = r_shunt_mohm if r_shunt_mohm is not None else cfg.get('r_shunt_mohm', 10050)

		# If SDA/SCL/i2c_freq/addr were not provided, fill from cfg or defaults
		self.sda_pin = sda_pin if sda_pin is not None else cfg.get('sda_pin', 21)
		self.scl_pin = scl_pin if scl_pin is not None else cfg.get('scl_pin', 22)
		self.i2c_freq = i2c_freq if i2c_freq is not None else cfg.get('i2c_freq', 100000)
		self.ina_addr = ina_addr if ina_addr is not None else cfg.get('ina_addr', 0x40)

		# create or use provided I2C
		self.i2c = i2c or self.init_i2c(self.sda_pin, self.scl_pin, self.i2c_freq)

		# initialize INA226
		try:
			self.ina = INA226(self.i2c, addr=self.ina_addr)
		except Exception as exc:
			raise RuntimeError("Failed to initialize INA226: {}".format(exc))

		# calibrate if requested
		if self.r_shunt_mohm is not None:
			try:
				self.ina.calibrate(r_shunt=self.r_shunt_mohm)
			except Exception as exc:
				# non-fatal: warn via print so the REPL user sees it
				print("Warning: failed to set custom calibration:", exc)

	@staticmethod
	def init_i2c(sda_pin=21, scl_pin=22, freq=100000):
		"""Create and return an I2C instance (MicroPython machine.I2C)."""
		try:
			return I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
		except Exception:
			return I2C(scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)

	def read(self):
		"""Read values from INA226 and return a dict with processed values.

		Returns:
			dict with keys: shunt_v (V), bus_v (V), current (A), current_mA (mA), power (W)
		"""
		try:
			shunt_v = self.ina.shunt_voltage / 1000.0
			bus_v = self.ina.bus_voltage
			current = self.ina.current + self.shunt_microampere_correction / 1000000.0
			power = self.ina.power
			current_mA = current * 1000.0

			return {
				"shunt_v": shunt_v,
				"bus_v": bus_v,
				"current": current,
				"current_mA": current_mA,
				"power": power,
			}

		except Exception as e:
			# bubble up exception so callers can handle or log it
			raise

	def run(self):
		"""Blocking loop: continuously read and print measurements to REPL."""
		print("Starting INA226 reader")
		print(
			"I2C SDA={}, SCL={}, addr=0x{:02x}, interval={}s".format(
				self.sda_pin, self.scl_pin, self.ina_addr, self.interval_seconds
			)
		)

		while True:
			try:
				d = self.read()
				print(
					"shunt_v={:.6f}V,bus_v={:.3f}V,current={:.6f}mA,power={:.6f}W".format(
						d["shunt_v"], d["bus_v"], d["current_mA"], d["power"]
					)
				)
			except Exception as e:
				print("Error reading INA226:", e)

			time.sleep(self.interval_seconds)