# RIGS Point of Sale

![RIGS POS](https://github.com/Elias0419/rigs_pos/assets/108772953/5048521c-06b2-4ab6-b2c9-016a41d7afa9)

This repository contains the Python source code and various support files for the **RIGS Point of Sale** software, a comprehensive touchscreen POS system using Kivy and Python, designed to run on Linux.

## Components
- **Installer** (`installer/rigs_pos_installer.sh`): An installation program written in Bash that supports `install mode` for installing dependencies, the software itself, a systemd service file, and several udev rules. `Demo mode` allows for testing without permanent system changes, cleaning up installation files on exit. Currently, supports Ubuntu, Fedora, Arch, and Gentoo.

- **Wrapper** (`wrapper.py`): Optionally used to start the program, maintain its running in case of failures, and send notifications via email or SMS about critical system events. 

- **Main** (`main.py`): The main entry point of the program; configures global Kivy settings and uses the Utilities module to instantiate classes, load settings, and create the main layout.

- **Popups** (`popups.py`): Manages the bulk of the GUI code, which consists mainly of Kivy popups.

- **Database Manager** (`database_manager.py`): Manages SQLite database operations, including creation, reading, and writing of tables for various functionalities like order management, history tracking, and inventory control.

### Modules Handling Hardware Interactions
- **Barcode Scanner** (`barcode_scanner.py`): Reads data from the barcode scanner and routes scanned data throughout the program.
- **Label Printer** (`label_printer.py`): Formats and prints barcode stickers.
- **Receipt Printer** (`receipt_printer.py`): Formats and prints branded receipts.
- **Open Cash Drawer** (`open_cash_drawer.py`): Opens the cash draw by sending some bytes of serial. 

## Dependencies
This project uses Kivy and KivyMD for GUI widgets and relies on specific Linux functionalities, particularly for hardware interactions like printers and barcode scanners.

## Acknowledgments
This project incorporates code from [barcode_scanner_python](https://github.com/vpatron/barcode_scanner_python) by Vince Patron, which is licensed under the MIT License.
