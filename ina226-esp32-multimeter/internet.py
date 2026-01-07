import network
from machine import idle
import config as config
from timeout import timeout
from time import sleep

def connect(reader=None, timeout_ms=12000):
    print('.', end='')
    sleep(0.1)

    nic = network.WLAN(network.STA_IF)

    print('.', end='')
    sleep(0.1)

    try:
        nic.ifconfig((
            config.ip['addr'],
            config.ip['mask'],
            config.ip['gw'],
            config.ip['dns']
        ))
    except AttributeError:
        pass

    print('.', end='')
    sleep(0.1)

    nic.active(True)
    print('.', end='')
    sleep(0.1)

    nic.connect(config.wlan['ssid'], config.wlan['psk'])

    print('.', end='')
    sleep(0.1)

    print('Connecting to WLAN %s...' % config.wlan['ssid'], end='')

    if timeout(nic.isconnected, timeout_ms):
        print('WLAN connect timed out')
        reader.pwr(False)
        import ds as ds
        ds.ds_interval_seconds()
        return False

    print(' connected')
    return True