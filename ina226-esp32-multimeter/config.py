'''
Config file.

usage:
> import config
> ssid = config.wlan['ssid']
'''

override = True


# WLAN Credentials
wlan = {
    'ssid': 'Rechnernetze',
    'psk' : 'rnFIW625'
}
if override:
    wlan = {
        'ssid':'DESKTOP',
        'psk':'9>8mF780'
    }


# Static ip config. Comment or remove to disable
# if override:
#     ip = {
#         'addr': '192.168.2.227',
#         'mask': '255.255.255.0',
#         'gw': '192.168.2.16',
#         'dns': '9.9.9.9'
#     }


def id():
    import machine
    from binascii import hexlify
    return hexlify(machine.unique_id()).decode('ascii')

id = id()

# mqtt credentials + topics
mqtt = {
    'id': 'umqtt_client',
    'host': '10.4.128.136',
    'port': 1883,
    'user': 'user1',
    'password': 'm9tQqvSpE3cLbYpt',
    'topics': {
        # EPD
        'current'   : 'ct/current',
    },
}
if override:
    mqtt['host'] = '192.168.178.28'
    mqtt['password'] = 'test'


# INA226 / current-reader configuration
# Values referenced by the `CurrentReader` wrapper and `main.py`.
ina226 = {
    'sda_pin': 21,
    'scl_pin': 22,
    'i2c_freq': 100000,
    'ina_addr': 0x40,
    'interval_seconds': 12, # reading interval in seconds
    'shunt_microampere_correction': -10, # microampere correction applied to INA226 current reading (in µA)
    'r_shunt_mohm': 10050, # shunt resistance used for calibration in mOhm (10.05 Ω -> 10050 mΩ)
    'pwr_pin': 25, #GPIO pin controlling power to INA226 trough AO3401 MOSFET
    'pwr_on_delay_ms': 100, #delay after powering on INA226 before it can be used
}

# shutdown at critical battery level
battery = {
    'enabled': True,
    'pin': {
        'bat_sense': 34,
        # 'ext_sense': 1 # not present on firebeetle
    },
    'meansby': 10,
    'critical': 0.1,
}