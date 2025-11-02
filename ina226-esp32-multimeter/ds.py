def ds(time):
    '''Put the MCU into deepsleep. Time in s (int)'''
    print('> deepsleep')
    from machine import deepsleep, Pin
    import esp32
    from time import sleep
    import config as config

    if not time == -1:
        print(f'wakeup in {time}s')
        sleep(0.1)
        print('good night')
        sleep(0.1)
        deepsleep(time*1000) # ms
    
    print('good night')
    sleep(0.1)
    deepsleep()
