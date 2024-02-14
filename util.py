import json
from kivymd.uix.button import MDRaisedButton
import time
import subprocess
import re
import threading
import dbus
from open_cash_drawer import open_cash_drawer
import sys
from kivy.clock import Clock

class Utilities:
    def __init__(self, ref):
        self.app = ref

    def toggle_category_selection(self, instance, category):
        if category in self.app.selected_categories:
            self.app.selected_categories.remove(category)
            instance.text = category
        else:
            self.app.selected_categories.append(category)
            instance.text = f"{category}\n (Selected)"

    def apply_categories(self):
        categories_str = ", ".join(self.app.selected_categories)
        self.app.popup_manager.add_to_db_category_input.text = categories_str
        self.app.popup_preloader.category_popup.dismiss()

    def reset_pin_timer(self):
        print("reset_pin_timer", self.app.pin_reset_timer)
        if self.app.pin_reset_timer is not None:
            self.app.pin_reset_timer.stop()

        #self.app.pin_reset_timer = self.app.pin_reset_timer(5.0, self.reset_pin)
        self.app.pin_reset_timer.start()

    def reset_pin(self, dt=None):  # Ensure dt=None is included to handle the callback argument from Clock.schedule_once
        print(f"reset pin\n{self.app.entered_pin}\n{self.app.popup_manager.pin_input.text}")
        def update_ui(dt):
            self.app.entered_pin = ""
            if self.app.popup_manager.pin_input is not None:
                self.app.popup_manager.pin_input.text = ""

        # Schedule the UI update to occur on the main thread
        Clock.schedule_once(update_ui)

    def calculate_common_amounts(self, total):
        amounts = []
        for base in [1, 5, 10, 20, 50, 100]:
            amount = total - (total % base) + base
            if amount not in amounts and amount >= total:
                amounts.append(amount)
        return amounts

    # def on_input_focus(self, instance, value):
    #     if value:
    #         instance.show_keyboard()
    #     else:
    #         instance.hide_keyboard()

    def update_clock(self, *args):
        self.app.clock_label.text = time.strftime("%I:%M %p\n%A\n%B %d, %Y\n")
        self.app.clock_label.color = self.get_text_color()

    def update_lockscreen_clock(self, *args):
        # self.app.popup_manager.clock_label.text = time.strftime("%I:%M %p\n%A\n%B %d, %Y\n")
        self.app.popup_manager.clock_label.text = time.strftime("%I:%M %p")
        self.app.popup_manager.clock_label.color = self.get_text_color()

    def get_text_color(self):
        if self.app.theme_cls.theme_style == "Dark":
            return (1, 1, 1, 1)
        else:
            return (0, 0, 0, 1)

    def reset_to_main_context(self, instance):
        self.app.current_context = "main"
        try:
            self.app.inventory_manager.detach_from_parent()
            self.app.label_manager.detach_from_parent()
        except Exception as e:
            print(e)


    def create_md_raised_button(
        self,
        text,
        on_press_action,
        size_hint=(None, None),
        font_style="Body1",
        height=50,
    ):
        button = MDRaisedButton(
            text=text,
            on_press=on_press_action,
            size_hint=size_hint,
            font_style=font_style,
            height=height,
        )
        return button

    def dismiss_popups(self, *popups):
        for popup_attr in popups:
            if hasattr(self, popup_attr):
                try:
                    popup = getattr(self, popup_attr)
                    if popup._is_open:
                        popup.dismiss()
                except Exception as e:
                    print(e)

    def update_display(self):
        print("called update display")
        self.app.order_layout.clear_widgets()
        for item_id, item_info in self.app.order_manager.items.items():
            item_name = item_info["name"]
            item_quantity = item_info["quantity"]
            item_total_price = item_info["total_price"]

            if item_quantity > 1:
                item_display_text = (
                    f"{item_name} x{item_quantity} ${item_total_price:.2f}"
                )
            else:
                item_display_text = f"{item_name} ${item_total_price:.2f}"

            item_button = MDRaisedButton(
                text=item_display_text,
                size_hint=(0.1, 0.1),
                halign="center",
                valign="center",
            )
            item_button.bind(
            on_press=lambda x, item_id=item_id: self.app.popup_manager.show_item_details_popup(item_id)
        )
            self.app.order_layout.add_widget(item_button)

    def update_financial_summary(self):
        subtotal = self.app.order_manager.subtotal
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        tax = self.app.order_manager.tax_amount
        discount = self.app.order_manager.order_discount  ########

        self.app.financial_summary_widget.update_summary(
            subtotal, tax, total_with_tax, discount
        )

    def manual_override(self, instance):

        current_time = time.time()
        print(f"{current_time}\n{self.app.override_tap_time}")
        if current_time - self.app.override_tap_time < 0.5:
            sys.exit(42)

        self.app.override_tap_time = current_time

    def set_primary_palette(self, color_name):
        self.app.theme_cls.primary_palette = color_name
        self.save_settings()

    def toggle_dark_mode(self):
        if self.app.theme_cls.theme_style == "Dark":
            self.app.theme_cls.theme_style = "Light"
        else:
            self.app.theme_cls.theme_style = "Dark"
        self.save_settings()

    def on_add_or_bypass_choice(self, choice_text, barcode):
        if choice_text == "Add Custom Item":
            self.app.popup_manager.show_custom_item_popup(barcode)
        elif choice_text == "Add to Database":
            self.app.popup_manager.show_add_to_database_popup(barcode)

    def initialze_categories(self):
        categories = [
            "Cdb",
            "Rig",
            "Nails",
            "Tubes",
            "Hand Pipes",
            "Chillum",
            "Ecig",
            "Butane",
            "Torch",
            "Toro",
            "Slides H",
            "Quartz",
            "Vaporizers",
            "Lighter",
            "9mm Thick",
            "Cleaning",
            "Edible",
            "Bubbler",
            "Sherlock",
            "Spoon",
            "Silicone",
            "Scales",
            "Slides",
            "Imported Glass",
            "Ash Catcher",
            "Soft Glass",
            "Vaporizers",
            "Pendant",
            "Smoker Accessory",
            "Ecig Accessories",
            "Happy Fruit",
            "Concentrate Accessories",
            "Conc. Devices, Atomizers",
            "Erigs And Accessory",
            "Mods Batteries Kits",
        ]
        return categories

    def dismiss_guard_popup(self):

        self.app.popup_manager.guard_popup.dismiss()
        #self.turn_on_monitor()

    def close_item_popup(self):
        self.dismiss_popups("item_popup")

    def dismiss_add_discount_popup(self):
        self.dismiss_popups("discount_popup")

    def dismiss_bypass_popup(self, instance, barcode):
        self.app.on_add_or_bypass_choice(instance.text, barcode)
        # self.dismiss_popups('popup')

    def close_add_to_database_popup(self):
        self.app.popup_manager.add_to_db_popup.dismiss()

    def on_cash_cancel(self, instance):
        self.app.popup_manager.cash_popup.dismiss()

    def on_adjust_price_cancel(self, instance):
        self.app.popup_manager.adjust_price_popup.dismiss()

    def on_custom_item_cancel(self, instance):
        self.app.popup_manager.custom_item_popup.dismiss()
        self.app.popup_manager.cash_input.text = ""

    def on_custom_cash_cancel(self, instance):
        self.app.popup_manager.custom_cash_popup.dismiss()

    def on_change_done(self, instance):
        self.app.popup_manager.change_popup.dismiss()
        self.app.popup_manager.show_payment_confirmation_popup()

    def split_cancel(self):
        self.app.popup_manager.dismiss_popups("split_payment_numeric_popup")
        self.app.popup_manager.finalize_order_popup.open()

    def split_on_cash_cancel(self):
        self.app.popup_manager.dismiss_popups("split_cash_popup")
        self.app.popup_manager.finalize_order_popup.open()

    def on_split_custom_cash_cancel(self, instance):
        self.app.popup_manager.dismiss_popups("split_custom_cash_popup")

    def trigger_guard_and_lock(self, trigger=False):

        if trigger:
            self.app.popup_preloader.lock_popup.open()
            self.app.is_lock_screen_displayed = True
        elif not self.app.is_guard_screen_displayed and not self.app.is_lock_screen_displayed:
            self.app.popup_preloader.lock_popup.open()
            self.app.popup_preloader.guard_popup.open()
            self.app.is_lock_screen_displayed = True
            self.app.is_guard_screen_displayed = True
        elif self.app.is_lock_screen_displayed and not self.app.is_guard_screen_displayed:
            self.app.popup_preloader.guard_popup.open()
            self.app.is_guard_screen_displayed = True


    def reboot(self, instance):
        try:
            subprocess.run(["systemctl", "reboot"])
        except Exception as e:
            print(e)

    def save_settings(self):
        settings = {
            "primary_palette": self.app.theme_cls.primary_palette,
            "theme_style": self.app.theme_cls.theme_style,
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f)

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                # Load theme settings
                self.app.theme_cls.primary_palette = settings.get("primary_palette", "Brown")
                self.app.theme_cls.theme_style = settings.get("theme_style", "Light")

                # # Check for emergency reboot flag
                # if settings.get("emergency_reboot", True):
                #     self.handle_emergency_reboot()

        except FileNotFoundError as e:
            print(e)


    # def handle_emergency_reboot(self):
    #     print("handle_emergency_reboot")
    #     with open("settings.json", "r+") as f:
    #         settings = json.load(f)
    #         settings["emergency_reboot"] = False
    #         f.seek(0)
    #         json.dump(settings, f)
    #         f.truncate()
    #     self.app.popup_manager.unrecoverable_error()

    def turn_on_monitor(self):
        try:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "1"], check=True
            )
        except Exception as e:
            print(e)





    def check_inactivity(self, *args):
        try:

            bus = dbus.SessionBus()
            screensaver_proxy = bus.get_object("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver")
            screensaver_interface = dbus.Interface(screensaver_proxy, dbus_interface="org.freedesktop.ScreenSaver")
            idle_time = screensaver_interface.GetSessionIdleTime()

            if idle_time > 600000:
                self.trigger_guard_and_lock(trigger=False)

            #return idle_time

        except Exception as e:
            print(f"Exception in check_inactivity\n{e}")


    def clear_split_numeric_input(self):
        self.app.popup_manager.split_payment_numeric_cash_input.text = ""

    def handle_split_input(self, amount, method):
        if not amount.strip():
            pass
        else:
            try:
                amount = float(amount)
                self.on_split_payment_confirm(amount=amount, method=method)
            except ValueError as e:
                print(e)

    def on_split_payment_confirm(self, amount, method):
        amount = float(f"{amount:.2f}")

        self.app.popup_manager.split_payment_info["total_paid"] += amount
        self.app.popup_manager.split_payment_info["remaining_amount"] -= amount
        self.app.popup_manager.split_payment_info["payments"].append(
            {"method": method, "amount": amount}
        )

        if method == "Cash":
            print("method", method)
            self.app.popup_manager.show_split_cash_popup(amount)
            self.app.popup_manager.split_payment_numeric_popup.dismiss()
        elif method == "Debit":
            self.app.popup_manager.show_split_card_confirm(amount, method)
            self.app.popup_manager.split_payment_numeric_popup.dismiss()
        elif method == "Credit":
            self.app.popup_manager.show_split_card_confirm(amount, method)
            self.app.popup_manager.split_payment_numeric_popup.dismiss()

    def split_cash_continue(self, instance):
        tolerance = 0.001
        self.app.popup_manager.dismiss_popups(
            "split_cash_popup", "split_cash_confirm_popup", "split_change_popup"
        )

        if abs(self.app.popup_manager.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.app.popup_manager.show_split_payment_numeric_popup(subsequent_payment=True)

    def split_card_continue(self, amount, method):

        tolerance = 0.001
        self.app.popup_manager.dismiss_popups("split_card_confirm_popup")

        if abs(self.app.popup_manager.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.app.popup_manager.show_split_payment_numeric_popup(subsequent_payment=True)

    def finalize_split_payment(self):
        self.app.order_manager.set_payment_method("Split")
        self.app.popup_manager.show_payment_confirmation_popup()

    def split_on_custom_cash_confirm(self, amount):

        self.app.popup_manager.split_custom_cash_popup.dismiss()
        input_amount = float(self.app.popup_manager.split_custom_cash_input.text)

        amount = float(amount)

        if input_amount > amount:

            open_cash_drawer()
            change = float(self.app.popup_manager.split_custom_cash_input.text) - amount

            self.app.popup_manager.split_cash_make_change(change, amount)
        else:

            open_cash_drawer()
            self.app.popup_manager.show_split_cash_confirm(amount)

    def split_on_cash_confirm(self, amount):
        self.app.popup_manager.split_cash_popup.dismiss()
        if float(self.app.popup_manager.split_cash_input.text) > amount:
            open_cash_drawer()
            change = float(self.app.popup_manager.split_cash_input.text) - amount

            self.app.popup_manager.split_cash_make_change(change, amount)
        else:

            open_cash_drawer()
            self.app.popup_manager.show_split_cash_confirm(amount)

    def indicate_incorrect_pin(self, layout):
        original_color = layout.background_color
        layout.background_color = [1, 0, 0, 1]
        Clock.schedule_once(lambda dt: setattr(layout, 'background_color', original_color), 0.5)

     # elif instance.text == "TEST": TODO
        #     print("test button")
        #     eel_thread = threading.Thread(target=self.start_eel)
        #     eel_thread.daemon = True
        #     eel_thread.start()


    def dismiss_single_discount_popup(self):
        self.app.popup_manager.discount_amount_input.text = ""
        self.app.popup_manager.discount_popup.dismiss()
    def dismiss_entire_discount_popup(self):
        self.app.popup_manager.discount_order_amount_input.text = ""
        self.app.popup_manager.discount_order_popup.dismiss()

class ReusableTimer:
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.timer = None

    def _run(self):
        self.function(*self.args, **self.kwargs)
        self.timer = None

    def start(self):
        if self.timer is not None:
            self.stop()
        self.timer = threading.Timer(self.interval, self._run)
        self.timer.start()

    def stop(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def reset(self):
        self.start()

