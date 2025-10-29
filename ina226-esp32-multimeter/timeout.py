def timeout(callback, ms):
    '''Calls repeatedly the callback until it returns True or the timeout 
    ms (int) is reached. '''
    from time import ticks_ms as millis
    from machine import idle

    timeout = millis() + ms
    while millis() < timeout:
        if callback():
            return False
        idle()
    return True