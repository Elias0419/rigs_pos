import subprocess
import time
import sys
import json
import requests

import logging

wrapper_logging_configured = False

def setup_logging():
    global wrapper_logging_configured
    if not wrapper_logging_configured:

        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler('wrapper.log')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                      datefmt='%m/%d/%Y %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter_console = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        ch.setFormatter(formatter_console)
        logger.addHandler(ch)

        logger.propagate = False

        wrapper_logging_configured = True
logger = logging.getLogger('wrapper')

class Wrapper:
    def __init__(self, ref=None):
        self.app = ref

        self.DEFAULT_CONFIG = {
            "script_path": "/home/rigs/rigs_pos/main.py",
            # "script_path": "/home/x/work/python/rigs_pos/main.py",
            "max_restarts": 3,
            "restart_window": 10,
            "recipient": "info@example.com",
        }

    def load_config(self):
        try:
            with open("/home/rigs/rigs_pos/wrapper_config.json", "r") as f:
                config = json.load(f)
        except Exception as e:
            config = self.DEFAULT_CONFIG
        return config

    def check_and_apply_updates(self):
        try:
            res = subprocess.run(["git", "pull"], capture_output=True, text=True)
            if "Already up to date." in res.stdout:
                logger.warn("[Wrapper]\nNo updates available")
                return False
            else:
                logger.warn("[Wrapper]\nApplication updated:\n" + res.stdout)
                return True
        except subprocess.CalledProcessError as e:
            logger.warn("[Wrapper]\nUpdate Error:", e)
        return

    def get_update_details(self):
        try:
            response = requests.get('https://raw.githubusercontent.com/Elias0419/rigs_pos/refs/heads/main/update/update_details')
            return response.text
        except:
            logger.warn("[Wrapper]: Couldn't get update details")
        return None


    def run_app(self, script_path, recipient, max_restarts, restart_window):
        recent_restarts = 0
        last_restart_time = time.time()

        while True:
            result = subprocess.run(["/home/rigs/0/bin/python", script_path])
            # result = subprocess.run(["/home/x/work/0/bin/python", script_path])
            current_time = time.time()
            if current_time - last_restart_time > restart_window:
                recent_restarts = 0
                last_restart_time = current_time

            if result.returncode in [0, 1, 42]:
                recent_restarts += 1
                if recent_restarts >= max_restarts:
                    self.send_email(
                        "App has failed!",
                        f"Script exited with returncode {result.returncode}.",
                        recipient,
                    )

                    # self.set_emergency_reboot_flag()
                    try:
                        fallback_process = subprocess.Popen(
                            [
                                "nohup",
                                "/home/rigs/1/bin/python",
                                "/home/rigs/fallback_rigs_pos/main.py",
                            ],
                            stdout=open("fallback_stdout.log", "w"),
                            stderr=open("fallback_stderr.log", "w"),
                        )
                        time.sleep(5)
                        if fallback_process.poll() is None:
                            self.send_email(
                                "Fallback successful",
                                "The application has successfully fallen back.",
                                recipient,
                            )
                            break
                        else:
                            self.send_email(
                                "Fallback Failed",
                                "The application has failed to fall back and is now stopped!",
                                recipient,
                            )
                            sys.exit(43)

                    except:
                        self.send_email(
                            "Fallback Failed",
                            "The application has failed to fall back and is now stopped!",
                            recipient,
                        )
                        sys.exit(43)
                continue
            elif result.returncode == 43:
                self.send_email(
                    "Alert",
                    "Script has been stopped with adminstrator's return code",
                    recipient,
                )
                break
            else:
                self.send_email(
                    "App has failed!",
                    f"Script has failed with unexpected return code: {result.returncode}",
                    recipient,
                )
                break

    # def set_emergency_reboot_flag(self):
    #
    #     with open("settings.json", "r+") as f:
    #         settings = json.load(f)
    #         settings["emergency_reboot"] = True
    #         f.seek(0)
    #         json.dump(settings, f)
    #         f.truncate()

    def send_email(self, subject, message, recipient):
        email_content = f"{subject}\n\n{message}"
        try:
            process = subprocess.run(
                ["msmtp", recipient], input=email_content, text=True
            )
        except Exception as e:
            logger.warn(e)

    def update_applied(self, details=None):
        if details:
            with open("update_applied", "w") as f:
                f.write(details)


if __name__ == "__main__":
    wrapper = Wrapper()
    config = wrapper.load_config()
    script_path = config["script_path"]
    recipient = config["recipient"]
    max_restarts = config["max_restarts"]
    restart_window = config["restart_window"]
    if wrapper.check_and_apply_updates():
        update_details = wrapper.get_update_details()
        if update_details:
            wrapper.update_applied(details=update_details)

    wrapper.run_app(script_path, recipient, max_restarts, restart_window)
