from lib.umqttsimple import MQTTClient
import binascii
import config as config


def get_client(reader=None):
    """Create and connect an MQTT client. Returns the connected client or
    None on failure (after calling ds interval fallback).
    """
    client = MQTTClient(
        binascii.hexlify(config.id),
        config.mqtt['host'],
        port=config.mqtt['port'],
        user=config.mqtt['user'],
        password=config.mqtt['password'],
        keepalive=60,
    )

    try:
        client.connect(timeout=4)
        return client
    except Exception:
        print('mqtt connect failed')
        try:
            reader.pwr(False)
            import ds as ds
            ds.ds_interval_seconds()
        except Exception:
            pass
        return None