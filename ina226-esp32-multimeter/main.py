import config
import time
import json
from current_reader import CurrentReader
import ds as ds
from time import sleep

def main():

    
    print('init network', end='')
    import internet
    from mqtt import mqtt

    print('Initializing CurrentReader...')
    try:
        reader = CurrentReader()
    except Exception as exc:
        print("Failed to initialize CurrentReader:", exc)
        return

    try:
        reader.pwr(True)
        sleep(1)  # wait a bit for INA to stabilize
        result = reader.read()
        print("Read result:", result)
        reader.pwr(False)
        
        from bat import bat_idle
        result["bat"] = bat_idle()

        mqtt.publish(
            config.mqtt['topics']['current'],
            json.dumps(result),
            qos=1
        )

    except Exception as exc:
        print("Error while running reader:", exc)

    ds.ds_interval_seconds()

if __name__ == "__main__":
    main()