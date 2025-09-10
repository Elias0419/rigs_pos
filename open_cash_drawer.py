import serial
import time
import logging
import stat
import os

logger = logging.getLogger("rigs_pos")


def open_cash_drawer(port="/dev/ttyUSB0", baudrate=9600):
    try:
        st = os.stat(port)
        if not stat.S_ISCHR(st.st_mode):
            raise FileNotFoundError
    except FileNotFoundError:
        logger.info("[open_cash_drawer] %s not present – skipped", port)
        return

    try:
        with serial.Serial(port, baudrate, timeout=0.2) as ser:
            ser.write(b"\x00")
            time.sleep(0.1)
    except (serial.SerialException, OSError) as exc:
        logger.warning("[open_cash_drawer] %s", exc, exc_info=True)


if __name__ == "__main__":
    open_cash_drawer()
