import os, json, socket, subprocess, time

SOCK_PATH = "/tmp/camview.sock"

def _send_cmd(cmd: dict, timeout=0.25):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(timeout)
    s.connect(SOCK_PATH); s.sendall(json.dumps(cmd).encode("utf-8")); s.close()

def open_or_raise_camview():
    # try to raise existing instance
    try:
        _send_cmd({"cmd": "raise"})
        return
    except Exception:
        pass


    subprocess.Popen(
        ["/home/rigs/0/bin/python3", "camview.py"],
        env=dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":0")),
        start_new_session=True,
    )

    for _ in range(20):
        time.sleep(0.1)
        try:
            _send_cmd({"cmd": "raise"})
            break
        except Exception:
            continue
