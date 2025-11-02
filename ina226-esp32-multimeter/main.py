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

    reader = CurrentReader()
    reader.pwr(True)
    print('power on')
    sleep(2)
    reader.pwr(False)
    print('power off')
 

    # print('Initializing CurrentReader...')
    # try:
    #     reader = CurrentReader()
    # except Exception as exc:
    #     print("Failed to initialize CurrentReader:", exc)
    #     return

    # try:
    #     sleep(2)
    #     result = reader.read()
    #     reader.power_off()

    #     mqtt.publish(
    #         config.mqtt['topics']['current'],
    #         json.dumps(result),
    #         qos=1
    #     )


    # except Exception as exc:
    #     print("Error while running reader:", exc)

    ds.ds_interval_seconds()


if __name__ == "__main__":
    main()