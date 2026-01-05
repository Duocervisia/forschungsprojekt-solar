import config as config
from machine import Pin, ADC
from time import sleep
from mqtt import mqtt
import json
from machine import deepsleep


_bat = ADC(Pin(config.battery['pin']['bat_sense'], Pin.IN))
_bat.atten(ADC.ATTN_11DB)
_bat.width(ADC.WIDTH_12BIT)

VREF = 3.578  # in volts, from eFuse or calibration

def read_battery_voltage():
    """
    Reads the battery voltage by averaging several ADC samples and applying the voltage divider correction.
    Returns a tuple: (averaged ADC value, voltage in volts (float)).
    """

    mean_cnt = config.battery['meansby']
    raw = 0
    for _ in range(mean_cnt):
        raw += _bat.read()
        sleep(0.01)
    raw //= mean_cnt

    # Convert ADC reading to voltage at the ADC pin
    # MicroPython ADC returns 0-4095 for 0-VREF (12 bit)
    # Vref = (4.22 * 4095) / raw
    # print(f'Vref: {Vref:.2f}V')
    measured_voltage = (raw / 4095) * VREF  # voltage at ADC pin
    battery_voltage = measured_voltage * 2    # correct for 1M+1M divider
    return raw, battery_voltage


def bat_idle():
    """
    call this method to do actions on low battery
    returns ADC value, voltage, and perc of the battery measurement

    ADC value range 0 (0.0v) - 4095 (3.3v)
    
    Battery Mapping
    3.3v 0% - 4.2v 100%
    """
    if not config.battery['enabled']:
        # Battery monitoring disabled
        return

    raw, voltage = read_battery_voltage()
    # Map voltage to percentage (3.3V = 0%, 4.2V = 100%)
    perc = max(min((voltage - 3.3) / (4.2 - 3.3), 1.0), 0.0)

    its_late = False
    if perc <= config.battery['critical']:
        e = f'Battery critical - {round(perc*100)}%, going to sleep'
        print(e)
        its_late = True
    print(f'Battery: {round(perc*100)}% ({voltage:.2f}V)')

    return {"voltage_V": voltage, "percentage": perc*100}