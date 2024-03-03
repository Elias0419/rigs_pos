import subprocess
import time
import sys
import json


class Wrapper():
    def __init__(self, ref=None):
        self.app = ref

        self.DEFAULT_CONFIG = {
            "script_path": "/home/rigs/rigs_pos/main.py",
            #"script_path": "/home/x/work/python/rigs_pos/main.py",
            "max_restarts": 3,
            "restart_window": 10,
            "recipient": "info@example.com",
        }

    def load_config(self):
        try:
            with open('/home/rigs/rigs_pos/wrapper_config.json', 'r') as f:
                config = json.load(f)
        except Exception as e:
            config = self.DEFAULT_CONFIG
        return config


    def run_app(self, script_path, recipient, max_restarts, restart_window):
        recent_restarts = 0
        last_restart_time = time.time()

        while True:
            result = subprocess.run(["/home/rigs/0/bin/python", script_path])
            #result = subprocess.run(["/home/x/work/python/0/bin/python", script_path])
            current_time = time.time()
            if current_time - last_restart_time > restart_window:
                recent_restarts = 0
                last_restart_time = current_time

            if result.returncode in [0, 1, 42]:
                recent_restarts += 1
                if recent_restarts >= max_restarts:
                    self.send_email("App has failed!",f"Script exited with returncode {result.returncode}.", recipient )

                    # self.set_emergency_reboot_flag()
                    try:
                        result = subprocess.run(["/home/rigs/1/bin/python", "/home/rigs/fallback_rigs_pos/main.py"])
                        if result:
                            self.send_email("Fallback successful","The application has successfully fallen back.", recipient)

                    except:
                        self.send_email("Fallback Failed","The application has failed to fall back and is now stopped!")
                        sys.exit(43)
                continue
            elif result.returncode == 43:
                self.send_email("Alert","Script has been stopped with adminstrator's return code", recipient )
                break
            else:
                self.send_email("App has failed!",f"Script has failed with unexpected return code: {result.returncode}",recipient )
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
            process = subprocess.run(["msmtp", recipient], input=email_content, text=True)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    wrapper=Wrapper()
    config = wrapper.load_config()
    script_path = config['script_path']
    recipient = config['recipient']
    max_restarts = config['max_restarts']
    restart_window = config['restart_window']
    wrapper.run_app(script_path, recipient, max_restarts, restart_window)

