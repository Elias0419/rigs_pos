#!/bin/bash

VENV_PATH="/home/rigs/0"
PROJECT_PATH="$HOME/postestdir"
SOURCES_LIST="/etc/apt/sources.list"
BACKUP_SOURCES_LIST="${SOURCES_LIST}.backup"
SERVICE_FILE="/etc/systemd/system/rigs_pos.service"
DEPENDENCIES="
appdirs==1.4.4
argcomplete==3.2.2
asyncgui==0.6.0
asynckivy==0.6.1
attrs==23.2.0
bottle==0.12.25
bottle-websocket==0.2.9
brother-ql==0.9.4
cachetools==5.3.3
certifi==2023.11.17
charset-normalizer==3.3.2
click==8.1.7
dbus-python==1.3.2
docutils==0.20.1
Eel==0.16.0
evdev==1.6.1
future==0.18.3
gevent==23.9.1
gevent-websocket==0.10.1
google-api-core==2.17.1
google-api-python-client==2.122.0
google-auth==2.28.2
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
googleapis-common-protos==1.63.0
greenlet==3.0.3
httplib2==0.22.0
idna==3.6
importlib-resources==6.1.1
Interface==2.11.1
Kivy==2.3.0
Kivy-Garden==0.1.5
kivymd==1.1.1
Levenshtein==0.25.0
materialyoucolor==2.0.5
oauthlib==3.2.2
packbits==0.6
pillow==10.2.0
protobuf==4.25.3
pyasn1==0.5.1
pyasn1-modules==0.3.0
Pygments==2.17.2
pynput==1.7.6
pyparsing==3.1.1
pypng==0.20220715.0
pyserial==3.5
python-barcode==0.15.1
python-escpos==3.1
python-xlib==0.33
pyusb==1.2.1
PyYAML==6.0.1
qrcode==7.4.2
rapidfuzz==3.6.1
requests==2.31.0
requests-oauthlib==1.4.0
rsa==4.9
setuptools==65.5.0
six==1.16.0
typing_extensions==4.9.0
uritemplate==4.1.1
urllib3==2.1.0
whichcraft==0.6.1
zope.event==5.0
zope.interface==6.3
zope.schema==7.0.1
"

if [ "$(ps -p 1 -o comm=)" != "systemd" ]; then
  echo "This system is not running systemd init."
  exit 1
fi
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
else
    echo "Unable to determine operating system."
    exit 1
fi
if [ "$(id -u)" != "0" ]; then
    echo "Please re-run this script with sudo."
    exit 1
fi
if [[ "$OS" == "Arch Linux" ]]; then
#     echo ""
#     echo "Press enter to continue or 'q' to quit"
#     read -r -n 1 input
#      if [[ $input == "q" ]]; then
#         echo "Bye!"
#         exit 1
#     else
    yes | pacman-key --init
    yes | pacman-key --populate archlinux
#     fi
fi

command_exists () {
    type "$1" &> /dev/null ;
}

install_python_package () {

    case "$1" in
        "Ubuntu"|"Debian")
            sudo apt-get install -y python3
            ;;
        "Fedora"|"CentOS")
            sudo dnf install -y python3
            ;;
        "Arch Linux")
            sudo pacman -S python --noconfirm
            ;;
        "Gentoo")
            sudo emerge python
            ;;
        *)
            echo "I haven't added support for $OS. Please install Python manually."
            exit 1
            ;;
    esac
}

install_git_package () {

    case "$1" in
        "Ubuntu"|"Debian")
            sudo apt-get install -y git
            ;;
        "Fedora"|"CentOS")
            sudo dnf install -y git
            ;;
        "Arch Linux")
            sudo pacman -S git --noconfirm
            ;;
        "Gentoo")
            sudo emerge git
            ;;
        *)
            echo "I haven't added support for $OS. Please install Git manually."
            exit 1
            ;;
    esac
}


if ! command_exists python3 ; then
    install_python=1
else
    install_python=0
fi
if ! command_exists git ; then
    install_git=1
else
    install_git=0
fi
if [[ $install_git == "1" ]] && [[ $install_python == "1" ]]; then
    # echo "Python and Git are not installed."
    # echo "Press enter to install them or q to quit"
    # read -r -n 1 input

    # if [[ $input == "q" ]]; then
    #     echo "Bye!"
    #     exit 1
    # else
    install_git_package "$OS"
    install_python_package "$OS"
    # fi
elif [[ $install_git == "1" ]] && [[ $install_python == "0" ]]; then
    # echo "Git is not installed."
    # echo "Press enter to install it or q to quit"
    # read -r -n 1 input

    # if [[ $input == "q" ]]; then
    #     echo "Bye!"
    #     exit 1
    # else
    install_git_package "$OS"
    # fi
elif [[ $install_git == "0" ]] && [[ $install_python == "1" ]]; then
    # echo "Python is not installed."
    # echo "Press enter to install it or q to quit"
    # read -r -n 1 input

    # if [[ $input == "q" ]]; then
    #     echo "Bye!"
    #     exit 1
    # else
    install_python_package "$OS"
    # fi
fi

PYTHON_VERSION=$(python3 -V | grep -oP 'Python \K[0-9]+\.[0-9]+')
if [[ $OS == "Ubuntu" ]]; then
    echo ""
    echo "On Ubuntu we need to install some build dependencies"
    echo ""
#     echo "Press enter to continue or 'q' to quit"
#     read -r -n 1 input
#      if [[ $input == "q" ]]; then
#         echo "Bye!"
#         exit 1
#     else

    cp ${SOURCES_LIST} ${BACKUP_SOURCES_LIST}
    if grep -q "^deb.*security.ubuntu.com.* universe" "$SOURCES_LIST"; then
        echo ""
    else
        sed -i '/^deb.*security.ubuntu.com.* main restricted$/s/main restricted/main restricted universe/' "$SOURCES_LIST"
    fi
    sudo apt-get update
    sudo apt-get install -y "python${PYTHON_VERSION}-venv" python3-dev build-essential cmake libdbus-1-dev libglib2.0-dev xclip
    #fi
fi
if [[ "$OS" == "Fedora Linux" ]]; then
    echo ""
    echo "On Fedora we need to install some build dependencies"
    echo ""
#     echo "Press enter to continue or 'q' to quit"
#     read -r -n 1 input
#      if [[ $input == "q" ]]; then
#         echo "Bye!"
#         exit 1
#     else
    sudo dnf install -y gcc python3-devel cmake dbus-devel glib2-devel xclip
#     fi
fi
if [[ "$OS" == "Arch Linux" ]]; then
    echo ""
    echo "On Arch we need to install some build dependencies"
#     echo ""
#     echo "Press enter to continue or 'q' to quit"
#     read -r -n 1 input
#      if [[ $input == "q" ]]; then
#         echo "Bye!"
#         exit 1
#     else
    pacman -S --noconfirm gcc cmake pkg-config xclip
#     fi
fi
# echo ""
# echo "WARNING: IF YOU ARE HERE TESTING THIS PLEASE CHOOSE DEMO MODE BELOW"
# echo "Press ctrl-c to quit now or:"
# echo "Press 'd' to enter demo mode or Enter to continue:"
# echo ""
# read -r -n 1 input
#
# if [[ $input == "d" ]]; then
#     demo_mode=1
# else
#     demo_mode=0
# fi

demo_mode=0
echo "


 _______ _________ _______  _______
(  ____ )\__   __/(  ____ \(  ____ |
| (    )|   ) (   | (    \/| (    \/
| (____)|   | |   | |      | (_____
|     __)   | |   | | ____ (_____  )
| (\ (      | |   | | \_  )      ) |
| ) \ \_____) (___| (___) |/\____) |
|/   \__/\_______/(_______)\_______)



"
if [[ $demo_mode -eq 1 ]]; then
    echo "Point of Sale Installation Program v0.1 (Demo)"
    echo ""
else
    echo "Point of Sale Installation Program v0.1"
    echo ""
fi
sleep 1

echo "Creating directories..."
echo ""
sleep 3


if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
echo "Installing dependencies..."
echo ""
sleep 1
echo "$DEPENDENCIES" | xargs pip install > /dev/null 2>&1

chown -R rigs /home/rigs/0
echo "Getting the application files..."
echo ""
sleep 1
cd /home/rigs
git clone https://github.com/Elias0419/rigs_pos > /dev/null 2>&1
chown -R rigs /home/rigs/rigs_pos

if [ "$demo_mode" -eq 1 ]; then
    echo "Application Installed Successfully!"
    echo ""
    sleep 1
    echo "Launching in 3..."
    sleep 1
    echo "Launching in 2..."
    sleep 1
    echo "Launching in 1..."
    sleep 1
    python${PYTHON_VERSION} main.py > /dev/null 2>&1 &
    PYTHON_PID=$!
    echo "That's it!"
    echo ""
    read -p "Press Enter to terminate the program and delete the installation files"
    echo "Cleaning up installation files..."
    kill $PYTHON_PID
    wait $PYTHON_PID 2>/dev/null
    rm -rf "$VENV_PATH"
    rm -rf "$HOME/rigs_pos"
    if [ -f "$BACKUP_SOURCES_LIST" ]; then
        mv -f "$BACKUP_SOURCES_LIST" "$SOURCES_LIST"
    fi
    echo "Bye!"
else
    cat <<EOF > $SERVICE_FILE
[Unit]
Description=Rigs Python Service
After=multi-user.target

[Service]
Type=simple
User=rigs
KillMode=process
WorkingDirectory=/home/rigs/rigs_pos
Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus"
Environment="DISPLAY=:0"
ExecStartPre=/usr/bin/sleep 10
ExecStart=/home/rigs/0/bin/python3 /home/rigs/rigs_pos/wrapper.py
[Install]
WantedBy=multi-user.target
EOF

    if [ "$OS" = "Ubuntu" ]; then
        sed -i 's|^Environment=.*|Environment=/run/user/1000/gdm/Xauthority|' $SERVICE_FILE
    fi
    systemctl enable rigs_pos
    if [ "$OS" == "Ubuntu" ]; then
        sudo sed -i 's/^#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf
        rm /usr/share/gnome-shell/extensions/ubuntu-appindicators@ubuntu.com/appIndicator.js
    fi

    bash -c 'cat > /etc/udev/rules.d/55-barcode-scanner.rules' <<EOF
SUBSYSTEM=="usb", ATTR{idVendor}=="05e0", ATTR{idProduct}=="1200", MODE="666"
EOF

    bash -c 'cat > /etc/udev/rules.d/99-labelprinter.rules' <<EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="04f9", ATTRS{idProduct}=="2043", MODE="0666"
EOF

    bash -c 'cat > /etc/udev/rules.d/99-receiptprinter.rules' <<EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", ATTRS{idProduct}=="0e28", MODE="0666"
EOF

    bash -c 'cat > /etc/udev/rules.d/99-usbserial.rules' <<EOF
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="23a3", MODE="0666"
EOF
systemctl disable installer_run_once.service

    reboot
fi
