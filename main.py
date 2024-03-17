# import logging
# from logger_conf import setup_logging
# setup_logging()
# logger = logging.getLogger(__name__)
# logger.info("Application starting..")


from kivy.config import Config
from kivy.core.window import Window
from kivy.modules import monitor, inspector
from kivymd.app import MDApp


from util import Utilities


#Config.set('kivy', 'keyboard_mode', 'systemanddock')
Config.set('input', 'isolution multitouch', 'hidinput,/dev/input/event12')
#Config.set('graphics', 'show_cursor', '0')
Config.set("graphics", "multisamples", "8")
Config.set('graphics', 'kivy_clock', 'interrupt')

Window.maximize()
Window.borderless = True


class CashRegisterApp(MDApp):
    def __init__(self, **kwargs):
        super(CashRegisterApp, self).__init__(**kwargs)


    def on_start(self):
        self.utilities.initialize_global_variables()
        self.utilities.load_settings()


    def build(self):
        self.utilities = Utilities(self)
        self.dual_pane_mode = False
        self.utilities.check_dual_pane_mode()
        if self.dual_pane_mode:
            self.utilities.instantiate_modules(module_name=None, dual_pane_mode=True) ##
            layout = self.utilities.create_main_layout(dual_pane_mode=True)
        else:
            self.utilities.instantiate_modules()
            layout = self.utilities.create_main_layout()
        return layout




if __name__ == "__main__":
    app = CashRegisterApp()
    app.run()
