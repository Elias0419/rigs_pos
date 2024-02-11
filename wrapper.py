
import time
import sys
import json

DEFAULT_CONFIG = {
    "script_path": "/home/rigs/rigs_pos/main.py",
    "max_restarts": 3,
    "restart_window": 10,
    "recipient": "info@example.com",
}

def load_config():
    try:
        with open('/home/rigs/rigs_pos/wrapper_config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        config = DEFAULT_CONFIG
    return config



def run_app(script_path, recipient, max_restarts, restart_window):
    recent_restarts = 0
    last_restart_time = time.time()

    while True:
        result = subprocess.run(["/home/rigs/0/bin/python", script_path])

        current_time = time.time()
        if current_time - last_restart_time > restart_window:
            recent_restarts = 0
            last_restart_time = current_time

        if result.returncode in [0, 1, 42]:
            recent_restarts += 1
            if recent_restarts >= max_restarts:
                send_email("App has failed!",f"Script exited with returncode {result.returncode}. Recent restart count: {recent_restarts}.", recipient )
#                 try:
        #             result = subprocess.run(["../1/bin/python", "/net/fallback/main_fallback.py"])
#
#                 except:
                sys.exit(43)
            continue
        elif result.returncode == 43:
            send_email("Alert","Script has been stopped with adminstrator's return code", recipient )
            break
        else:
            send_email("App has failed!",f"Script has failed with unexpected return code: {result.returncode}",recipient )
            break

def send_email(subject, message, recipient):
    email_content = f"{subject}\n\n{message}"
    try:
        process = subprocess.run(["msmtp", recipient], input=email_content, text=True)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    config = load_config()
    script_path = config['script_path']
    recipient = config['recipient']
    max_restarts = config['max_restarts']
    restart_window = config['restart_window']
    run_app(script_path, recipient, max_restarts, restart_window)
