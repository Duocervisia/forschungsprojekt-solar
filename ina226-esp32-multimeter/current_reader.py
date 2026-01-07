
import time
from machine import I2C, Pin
from lib.ina226 import INA226
import esp32

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
		r_shunt_mohm=None,
		v_shunt_drop_voltage_at_max_current_mv=None,
		i2c=None,
	):
		"""Initialize reader.

		Parameters:
			sda_pin, scl_pin, i2c_freq: I2C bus pins and frequency.
			ina_addr: I2C address of the INA226.
			interval_seconds: sleep between measurements in `run()`.
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

		# Power control (optional): configure pwr_pin from config if available.
		self.pwr_pin_cfg = cfg.get('pwr_pin')
		self.pwr_pin = None
		self.pwr_on_delay_ms = cfg.get('pwr_on_delay_ms', 20)

		self.interval_seconds = interval_seconds if interval_seconds is not None else cfg.get('interval_seconds', 2)
		self.r_shunt_mohm = r_shunt_mohm if r_shunt_mohm is not None else cfg.get('r_shunt_mohm', 10050)
		self.v_shunt_drop_voltage_at_max_current_mv = v_shunt_drop_voltage_at_max_current_mv if v_shunt_drop_voltage_at_max_current_mv is not None else cfg.get('v_shunt_drop_voltage_at_max_current_mv', 10.0)

		# If SDA/SCL/i2c_freq/addr were not provided, fill from cfg or defaults
		self.sda_pin = sda_pin if sda_pin is not None else cfg.get('sda_pin', 21)
		self.scl_pin = scl_pin if scl_pin is not None else cfg.get('scl_pin', 22)
		self.i2c_freq = i2c_freq if i2c_freq is not None else cfg.get('i2c_freq', 100000)
		self.ina_addr = ina_addr if ina_addr is not None else cfg.get('ina_addr', 0x40)
		self.current_multiplicative_correction = cfg.get('current_multiplicative_correction', 1.0)
		self.current_additive_correction = cfg.get('current_additive_correction', 0.0)

		# create or use provided I2C
		self.i2c = i2c or self.init_i2c(self.sda_pin, self.scl_pin, self.i2c_freq)

		# Power control (optional): configure pwr_pin from config if available.
		
		# INA object is created only when powering on to avoid touching the bus when
		# the INA226 is unpowered.
		self.ina = None

		# track whether we've powered the INA on via pwr(); starts as False
		self._powered = False

		# calibration will be applied when INA is initialized (after powering on)

	@staticmethod
	def init_i2c(sda_pin=21, scl_pin=22, freq=100000):
		"""Create and return an I2C instance (MicroPython machine.I2C)."""
		try:
			return I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
		except Exception:
			return I2C(scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)

	def read(self, samples=1, delay=1):
		"""Read values from INA226.

		If `samples` > 1, take multiple readings and return the median for each
		measured key. `delay` controls seconds between samples;.

		Returns a dict with keys: `shunt_V`, `bus_V`, `current_A`.
		"""
		# At this point the caller must ensure the INA is powered and initialized
		# (call pwr(True) before calling read()). We do not change power here.
		if self.ina is None:
			raise RuntimeError("INA not initialized. Call pwr(True) before read().")
		
		print("Taking readings... ", end='')

		def _single_read():
			shunt_v = self.ina.shunt_voltage / 1000.0
			bus_v = self.ina.bus_voltage
			current = self.ina.current
			return {"shunt_V": shunt_v, "bus_V": bus_v, "current_A": current}
		
		def _median(vals):
			s = sorted(vals)
			n = len(s)
			mid = n // 2
			if n % 2 == 1:
				return s[mid]
			return (s[mid - 1] + s[mid]) / 2

		# single sample fast path
		if not samples or samples <= 1:
			return _single_read()

		# collect samples
		raw = []
		for i in range(int(samples)):
			raw.append(_single_read())
			print(i+1, end=' ')
			if i + 1 < samples:
				time.sleep(delay)

		print(' done')
		print('Computing medians...', end='')

		# compute medians
		keys = set()
		for rr in raw:
			keys.update(rr.keys())
		result = {}
		for k in keys:
			vals = [rr[k] for rr in raw if k in rr]
			if vals:
				result[k] = _median(vals)
		print('done')
		print("Read result (medians):", result)
		return result

	def pwr(self, on):
		"""Control power to the INA226.

		Parameters:
			on (bool): True to power ON (drive MOSFET gate low), False to power OFF.

		This method is idempotent. When powering ON it will initialize the INA
		object (and apply calibration). When powering OFF it will deinitialize the
		INA object and attempt to enable pin hold so the pin state persists during
		deep sleep.
		"""
		if on:
			if self._powered:
				return
			print("Powering on INA226...",end='')
			# drive low to power on (active-low MOSFET gate)
			try:
				esp32.gpio_deep_sleep_hold(False)
				self.pwr_pin = Pin(self.pwr_pin_cfg, Pin.OUT, value=0, hold=False)
			except Exception:
				pass
			# wait for device to become ready
			time.sleep(self.pwr_on_delay_ms / 1000.0)
			# initialize INA if not present
			if self.ina is None:
				try:
					self.ina = INA226(self.i2c, addr=self.ina_addr)
					if self.r_shunt_mohm is not None:
						try:
							self.ina.calibrate(r_shunt=self.r_shunt_mohm, v_shunt=self.v_shunt_drop_voltage_at_max_current_mv)
						except Exception as exc:
							print("Warning: failed to set custom calibration:", exc)
				except Exception as exc:
					raise RuntimeError("Failed to initialize INA226: {}".format(exc))
			self._powered = True
			print(" done")
		else:
			# power off
			print("Powering off INA226... ",end='')
			print(self._powered)
			if not self._powered:
				return
			print(self.pwr_pin)
			try:
				esp32.gpio_deep_sleep_hold(True)
				self.pwr_pin = Pin(self.pwr_pin_cfg, Pin.OUT, value=1, hold=True)
			except Exception:
				pass
			# deinitialize INA reference; will be recreated on next power-on
			self.ina = None
			self._powered = False
