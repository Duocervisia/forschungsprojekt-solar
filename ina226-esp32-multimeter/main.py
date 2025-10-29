import config
import time
import json
from current_reader import CurrentReader

def main():
    try:
        reader = CurrentReader()
    except Exception as exc:
        print("Failed to initialize CurrentReader:", exc)
        return
    
    print('init network', end='')
    import internet
    from mqtt import mqtt
    

    try:
        result = reader.read()

        mqtt.publish(
            config.mqtt['topics']['current'],
            json.dumps(result)
        )


    except KeyboardInterrupt:
        # allow clean stop from REPL if supported on the port
        print("Interrupted")
    except Exception as exc:
        print("Error while running reader:", exc)


if __name__ == "__main__":
    main()