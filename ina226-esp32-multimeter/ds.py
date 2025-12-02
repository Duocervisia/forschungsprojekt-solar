def ds(time):
    '''Put the MCU into deepsleep. Time in ms (int)'''
    print('> deepsleep')
    from machine import deepsleep, Pin
    import esp32
    from time import sleep
    import config as config

    if not time == -1:
        print(f'wakeup in {time}ms')
        sleep(0.1)
        print('good night')
        sleep(0.1)
        deepsleep(time) # ms
    
    print('good night')
    sleep(0.1)
    deepsleep()

def ds_interval_seconds():
    '''Put the MCU into deepsleep for the configured interval seconds'''
    import config as config
    from machine import deepsleep, Pin
    import time

    print("main end ticks_ms:", time.ticks_ms())
    deepsleep(config.ina226['interval_seconds'] * 1000 - time.ticks_ms())