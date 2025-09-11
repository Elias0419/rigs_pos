import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from kivy.config import Config

Config.set("graphics", "width", "1920")
Config.set("graphics", "height", "1080")
# Config.set('graphics', 'show_cursor', '0')
Config.set("graphics", "multisamples", "8")
Config.set("graphics", "kivy_clock", "interrupt")
Config.set("kivy", "exit_on_escape", "0")

from kivymd.app import MDApp

from util import setup_logging, Utilities

setup_logging()
import logging

logger = logging.getLogger("rigs_pos")


class RigsPOS(MDApp):
    def __init__(self, **kwargs):
        super(RigsPOS, self).__init__(**kwargs)
        self.utilities = Utilities(self)
        self.logged_in_user = "nobody"
        self.is_rigs = self.utilities.is_rigs()
        if self.is_rigs:
            self.admin = False
        else:
            self.admin = True

    def on_start(self):
        self.utilities.initialize_global_variables()
        self.utilities.load_settings()
        self.utilities.resume_or_lock()

    def build(self):
        self.utilities.instantiate_modules()
        self.utilities.register_fonts()
        layout = self.utilities.create_main_layout()
        return layout


if __name__ == "__main__":
    app = RigsPOS()
    try:
        app.run()
    except KeyboardInterrupt:
        print("Exiting...")
