from lib.umqttsimple import MQTTClient
import binascii
import config as config

mqtt = MQTTClient(
    binascii.hexlify(config.id),
    config.mqtt['host'],
    port = config.mqtt['port'],
    user = config.mqtt['user'],
    password = config.mqtt['password'],
    keepalive = 60
)

try:
    mqtt.connect(timeout=4)
except:
    print('mqtt connect failed')
    from ds import ds
    ds(24*60*60)