import serial
import time


def open_cash_drawer(port="/dev/ttyUSB0", baudrate=9600):
    try:
        with serial.Serial(port, baudrate) as ser:
            ser.write(b"\x00")
            time.sleep(1)
    except serial.SerialException as e:
        print(e)
        pass


if __name__ == "__main__":
    open_cash_drawer()
