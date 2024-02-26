import dbus
import subprocess
import time
import threading  # Import threading module

class InactivityChecker:
    def check_inactivity_dbus(self):
        while True:
            try:
                bus = dbus.SessionBus()
                screensaver_proxy = bus.get_object(
                    "org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver"
                )
                screensaver_interface = dbus.Interface(
                    screensaver_proxy, dbus_interface="org.freedesktop.ScreenSaver"
                )
                idle_time = screensaver_interface.GetSessionIdleTime()

                hours, remainder = divmod(idle_time, 3600000)
                minutes, seconds = divmod(remainder, 60000)
                seconds //= 1000

                human_readable_time = f"{hours}h:{minutes}m:{seconds}s"

                if idle_time > 6000:
                    print(f"[DBus] Idle time: {human_readable_time} - Triggering guard and lock")
                    self.trigger_guard_and_lock(trigger=False)
                    break
                else:
                    print(f"[DBus] Current idle time: {human_readable_time}")
                    time.sleep(1)
            except Exception as e:
                print(f"[DBus] Exception in check_inactivity: {e}")
                break

    def check_inactivity_xprintidle(self):
        while True:
            try:
                idle_time_output = subprocess.check_output(["xprintidle"]).decode().strip()
                idle_time = int(idle_time_output)

                if idle_time > 6000:
                    print(f"[xprintidle] Idle time: {idle_time}ms - Triggering guard and lock")
                    self.trigger_guard_and_lock(trigger=False)
                    break
                else:
                    print(f"[xprintidle] Current idle time: {idle_time}ms")
                    time.sleep(1)
            except Exception as e:
                print(f"[xprintidle] Exception in check_inactivity: {e}")
                break

    def trigger_guard_and_lock(self, trigger):
        print(f"Guard and lock triggered: {trigger}")

if __name__ == "__main__":
    checker = InactivityChecker()

    dbus_thread = threading.Thread(target=checker.check_inactivity_dbus)
    xprintidle_thread = threading.Thread(target=checker.check_inactivity_xprintidle)

    dbus_thread.start()
    xprintidle_thread.start()

    dbus_thread.join()
    xprintidle_thread.join()
