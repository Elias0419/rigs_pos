import subprocess
import time


def run_app(script_path="main.py", max_restarts=3, restart_window=10):
    recent_restarts = 0
    last_restart_time = time.time()

    while True:
        result = subprocess.run(["../0/bin/python", script_path])

        current_time = time.time()
        if current_time - last_restart_time > restart_window:
            recent_restarts = 0
            last_restart_time = current_time

        if result.returncode in [0, 1, 42]:
            recent_restarts += 1
            if recent_restarts >= max_restarts:
                try:
                    print("test")
                    # result = subprocess.run(["../1/bin/python", "/net/fallback/main_fallback.py"])
                    # TODO logging and send email/text
                    # TODO wrapper-ception instead of calling fallback directly?
                except:
                    break
            continue
        elif result.returncode == 43:
            break
        else:
            break


if __name__ == "__main__":
    run_app()
