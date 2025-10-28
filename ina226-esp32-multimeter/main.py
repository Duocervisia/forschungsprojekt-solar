import time

print("Serial print example — messages appear on the serial REPL")
counter = 0

while True:
    # Print a simple counter once per second. On the ESP32 this goes to the USB serial/repl.
    print("counter:", counter)
    counter += 10
    time.sleep(1)