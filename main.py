from kivy.config import Config
Config.set('graphics', 'width', '1920')
Config.set('graphics', 'height', '1080')
#Config.set('graphics', 'show_cursor', '0')
Config.set("graphics", "multisamples", "8")
Config.set("graphics", "kivy_clock", "interrupt")
Config.set("kivy", "exit_on_escape", "0")

from kivymd.app import MDApp
from kivy.core.window import Window

from kivy.core.text import LabelBase
LabelBase.register(
    name="Emoji",
    fn_regular="images/seguiemj.ttf"
)

from util import setup_logging, Utilities
setup_logging()
import logging
logger = logging.getLogger('rigs_pos')

class CashRegisterApp(MDApp):
    def __init__(self, **kwargs):
        super(CashRegisterApp, self).__init__(**kwargs)
        self.utilities = Utilities(self)
        self.logged_in_user = "nobody"
        if self.utilities.is_rigs():
            self.admin = False
        else:
            self.admin = True

    def on_start(self):
        self.utilities.initialize_global_variables()
        self.utilities.load_settings()

    def build(self):
        self.utilities.instantiate_modules()
        layout = self.utilities.create_main_layout()
        return layout


if __name__ == "__main__":
    app = CashRegisterApp()
    try:
        app.run()
    except KeyboardInterrupt:
        print("Exiting...")
