import subprocess
import time
import sys
import json
import logging

logger = logging.getLogger('wrapper')
wrapper_logging_configured = False

def setup_logging():

    global wrapper_logging_configured
    if not wrapper_logging_configured:
        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler('wrapper.log')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S'
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter_console = logging.Formatter(
            '%(name)-12s: %(levelname)-8s %(message)s'
        )
        ch.setFormatter(formatter_console)
        logger.addHandler(ch)

        logger.propagate = False
        wrapper_logging_configured = True

setup_logging()

class Wrapper:
    def __init__(self):
        logger.info("""\n
        APPLICATION START
        \n""")

        self.DEFAULT_CONFIG = {
            "script_path": "/home/rigs/rigs_pos/main.py",
            "recipient": "info@example.com",
        }
        self.config = self.load_config()
        self.crash_count = 0
        self.max_crashes = 3

    def load_config(self):
        try:
            with open("/home/rigs/rigs_pos/wrapper_config.json", "r") as f:
                config = json.load(f)
        except Exception:
            logger.warning("Could not load /home/rigs/rigs_pos/wrapper_config.json; using defaults.")
            config = self.DEFAULT_CONFIG
        return config

    def run_app(self):
        while True:
            process = subprocess.Popen([
                "/home/rigs/0/bin/python3",
                self.config["script_path"]
            ])
            ret_code = process.wait()

            if ret_code == 42:
                logger.info("Received admin code 42. Stopping wrapper loop.")
                break
            else:
                self.crash_count += 1
                logger.warning(f"Application ended with returncode {ret_code}. Crash count: {self.crash_count}")

                # If crash count hits the threshold, send email and reboot.
                if self.crash_count >= self.max_crashes:
                    self.send_email(
                        subject="Application Crash Alert",
                        message=(
                            f"The application has crashed {self.crash_count} times.\n"\
                            "Initiating system reboot."
                        ),
                        recipient=self.config["recipient"]
                    )
                    logger.error("Max crash count reached. Rebooting the system now.")

                    try:
                        subprocess.run(["reboot"], check=True)
                    except Exception as e:
                        logger.error(f"Failed to reboot: {e}")
                        sys.exit(1)


    def send_email(self, subject, message, recipient):

        email_content = f"{subject}\n\n{message}"
        try:
            subprocess.run(
                ["msmtp", recipient],
                input=email_content,
                text=True,
                check=True
            )
            logger.info("Crash notification email sent.")
        except Exception as e:
            logger.warning(f"Failed to send email: {e}")

if __name__ == "__main__":
    wrapper = Wrapper()
    wrapper.run_app()


"""
--------------------------------------------------------------------------------
old wrapper code
--------------------------------------------------------------------------------

import subprocess
import time
import sys
import json
import datetime
import requests

import logging
logger = logging.getLogger('wrapper')
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
setup_logging()

class Wrapper:
    def __init__(self, ref=None):
        self.app = ref

        self.DEFAULT_CONFIG = {
            # "script_path": "/home/rigs/rigs_pos/main.py",
            "script_path": "/home/x/work/python/rigs_pos/main.py",
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
        print("called check")
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
        last_update_check_date = None

        while True:
            # Start the application
            # process = subprocess.Popen(["/home/rigs/0/bin/python", script_path])
            process = subprocess.Popen(["/home/x/work/rigs_pos_venv/bin/python3", script_path])
            time.sleep(1)
            while True:
                time.sleep(1)

                current_time = time.time()
                current_date = datetime.date.today()
                now = datetime.datetime.now()

                if now.hour == 1 and last_update_check_date != current_date:
                    last_update_check_date = current_date

                    if self.check_and_apply_updates():
                        update_details = self.get_update_details()
                        if update_details:
                            self.update_applied(details=update_details)

                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()

                        break

                if process.poll() is not None:
                    result_returncode = process.returncode
                    if current_time - last_restart_time > restart_window:
                        recent_restarts = 0
                        last_restart_time = current_time

                    if result_returncode in [0, 1, 42]:
                        recent_restarts += 1
                        if recent_restarts >= max_restarts:
                            self.send_email(
                                "App has failed!",
                                f"Script exited with returncode {result_returncode}.",
                                recipient,
                            )

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
                                    sys.exit(0)
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
                        # Break the inner loop to restart the application
                        break
                    elif result_returncode == 43:
                        self.send_email(
                            "Alert",
                            "Script has been stopped with administrator's return code",
                            recipient,
                        )
                        sys.exit(43)
                    else:
                        self.send_email(
                            "App has failed!",
                            f"Script has failed with unexpected return code: {result_returncode}",
                            recipient,
                        )
                        sys.exit(43)

    def send_email(self, subject, message, recipient):
        email_content = f"{subject}\\n\\n{message}"
        try:
            process = subprocess.run(
                ["msmtp", recipient], input=email_content, text=True
            )
        except Exception as e:
            logger.warn(e)

    def update_applied(self, details=None):
        with open("update_applied", "w") as f:
            f.write("")
        if details:
            with open('update/update_details', "w") as f:
                f.write(details)

if __name__ == "__main__":
    wrapper = Wrapper()
    config = wrapper.load_config()
    script_path = config["script_path"]
    recipient = config["recipient"]
    max_restarts = config["max_restarts"]
    restart_window = config["restart_window"]

    wrapper.run_app(script_path, recipient, max_restarts, restart_window)
"""
