import config
import time
import json
from current_reader import CurrentReader
import ds as ds
from time import sleep
import internet
from mqtt import get_client

def main():

    print('Initializing CurrentReader...', end='')
    try:
        reader = CurrentReader()
    except Exception as exc:
        print("Failed to initialize CurrentReader:", exc)
        return
    print(' done')

    reader.pwr(True)

    print('init network', end='')
    # establish network connection before proceeding; pass reader so
    # internet can power down the reader on timeout
    if not internet.connect(reader):
        return
    mqttClient = get_client(reader)
    if not mqttClient:
        return

    try:
        result = reader.read(samples=3)
        reader.pwr(False)
        
        from bat import bat_idle
        result["bat"] = bat_idle()

        mqttClient.publish(
            config.mqtt['topics']['current'],
            json.dumps(result),
            qos=1
        )

    except Exception as exc:
        print("Error while running reader:", exc)

    ds.ds_interval_seconds()

if __name__ == "__main__":
    main()