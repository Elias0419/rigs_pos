# RIGS Point of Sale

![RIGS POS](https://github.com/Elias0419/rigs_pos/assets/108772953/5048521c-06b2-4ab6-b2c9-016a41d7afa9)

This repository contains the Python source code and various support files for the **RIGS Point of Sale** software.

## Dependencies
This project uses Kivy and KivyMD for GUI widgets and relies on specific Linux functionalities, particularly for hardware interactions like printers and barcode scanners.

## Acknowledgments
This project incorporates code from [barcode_scanner_python](https://github.com/vpatron/barcode_scanner_python) by Vince Patron, which is licensed under the MIT License.

## Note
Note that this project is probably not useful to you as a general purpose point of sale. It's designed for a very specific use case. It would need, at the very least, some tinkering to change hardcoded paths, hardware-specific settings (e.g. printers) and operating system interactions (e.g. system services, udev rules, drivers, etc...)
