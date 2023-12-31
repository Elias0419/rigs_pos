import serial
import time

def open_cash_drawer(port="/dev/ttyUSB0", baudrate=9600):

    try:
        with serial.Serial(port, baudrate) as ser:
            # Sending a dummy byte to trigger the drawer
            ser.write(b'\x00')
            time.sleep(1)
        print("Cash drawer opened successfully.")
    except serial.SerialException as e:
        print(f"Error opening cash drawer: {e}")
if __name__ == "__main__":
    print("Press enter to open the cash drawer.")
    response = input()
    if response == "":
        print("DEBUG cash drawer triggered")
        open_cash_drawer()
    # else:
    #     return
