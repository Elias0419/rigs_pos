#!/bin/bash

VENV_PATH="$HOME/postestvenv"
PROJECT_PATH="$HOME/postestdir"
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
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
else
    echo "Unable to determine operating system."
    exit 1
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
            sudo pacman -Sy python
            ;;
        "Gentoo")
            sudo emerge -Sy python
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
            sudo pacman -Sy git
            ;;
        "Gentoo")
            sudo emerge -Sy git
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
    echo "Python and Git are not installed."
    echo "Press enter to install them or q to quit"
    read -r -n 1 input

    if [[ $input == "q" ]]; then
        echo "Bye!"
        exit 1
    else
        install_git_package "$OS"
        install_python_package "$OS"
    fi
elif [[ $install_git == "1" ]] && [[ $install_python == "0" ]]; then
    echo "Git is not installed."
    echo "Press enter to install it or q to quit"
    read -r -n 1 input

    if [[ $input == "q" ]]; then
        echo "Bye!"
        exit 1
    else
        install_git_package "$OS"
    fi
elif [[ $install_git == "0" ]] && [[ $install_python == "1" ]]; then
    echo "Python is not installed."
    echo "Press enter to install it or q to quit"
    read -r -n 1 input

    if [[ $input == "q" ]]; then
        echo "Bye!"
        exit 1
    else
        install_python_package "$OS"
    fi
fi
if [[ $OS == "Ubuntu" ]]; then
    echo ""
    echo "On Ubuntu we need to install some build dependencies"
    echo "Press enter to continue or 'q' to quit"
    read -r -n 1 input
     if [[ $input == "q" ]]; then
        echo "Bye!"
        exit 1
    else
        sudo apt-get install -y python3.12-venv python3-dev build-essential cmake libdbus-1-dev
    fi
fi
if [[ $OS == "Fedora Linux" ]]; then
    echo ""
    echo "On Fedora we need to install some build dependencies"
    echo "Press enter to continue or 'q' to quit"
    read -r -n 1 input
     if [[ $input == "q" ]]; then
        echo "Bye!"
        exit 1
    else
        sudo dnf install -y gcc python3-devel cmake dbus-devel glib2-devel
    fi
fi
echo ""
echo ""
echo "Press 'd' to enter demo mode or Enter to continue:"
read -r -n 1 input

if [[ $input == "d" ]]; then
    demo_mode=1
else
    demo_mode=0
fi


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
else
    echo "Point of Sale Installation Program v0.1"
fi
sleep 1
echo "Creating directories..."
sleep 3


if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
echo "Installing dependencies..."
sleep 1
echo "$DEPENDENCIES" | xargs pip install > /dev/null 2>&1


echo "Getting the application files..."
sleep 1
git clone https://github.com/Elias0419/rigs_pos > /dev/null 2>&1
cd rigs_pos
mkdir saved_orders
echo "Application Installed Successfully!"
sleep 1
echo "Launching in 3..."
sleep 1
echo "Launching in 2..."
sleep 1
echo "Launching in 1..."
sleep 1
python3 main.py > /dev/null 2>&1 &
PYTHON_PID=$!

if [[ $demo_mode -eq 1 ]]; then
    echo "That's it!"
    read -p "Press Enter to terminate the program and delete the installation files"
    echo "Cleaning up installation files..."
    kill $PYTHON_PID
    wait $PYTHON_PID 2>/dev/null
    rm -rf "$VENV_PATH"
    rm -rf "$HOME/rigs_pos"
    echo "Bye!"
else
    echo "Other setup for the real installation goes here"
    echo "But for now we're just going to delete the installation files and quit"
    read -p "Press Enter to continue"
    kill $PYTHON_PID
    wait $PYTHON_PID 2>/dev/null
    rm -rf "$VENV_PATH"
    rm -rf "$HOME/rigs_pos"
    echo "Bye!"
fi
