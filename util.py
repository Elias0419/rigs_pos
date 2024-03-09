import json
import time
import subprocess
import threading
import sys
import random

import dbus
from kivy.clock import Clock
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivy.uix.textinput import TextInput
from open_cash_drawer import open_cash_drawer
from barcode.upc import UniversalProductCodeA as upc_a
from kivy.core.window import Window
from receipt_printer import ReceiptPrinter
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import GridLayout

class Utilities:
    def __init__(self, ref):
        self.app = ref

    # def toggle_category_selection(self, instance, category):
    #     if category in self.app.selected_categories:
    #         self.app.selected_categories.remove(category)
    #         instance.text = category
    #     else:
    #         self.app.selected_categories.append(category)
    #         instance.text = f"{category}\n (Selected)"


    def reset_pin_timer(self):
        print("reset_pin_timer", self.app.pin_reset_timer)
        if self.app.pin_reset_timer is not None:
            self.app.pin_reset_timer.stop()

        self.app.pin_reset_timer.start()

    def reset_pin(self, dt=None):
        print(
            f"reset pin\n{self.app.entered_pin}\n{self.app.popup_manager.pin_input.text}"
        )

        def update_ui(dt):
            self.app.entered_pin = ""
            if self.app.popup_manager.pin_input is not None:
                self.app.popup_manager.pin_input.text = ""

        Clock.schedule_once(update_ui)

    def calculate_common_amounts(self, total):
        amounts = []
        for base in [1, 5, 10, 20, 50, 100]:
            amount = total - (total % base) + base
            if amount not in amounts and amount >= total:
                amounts.append(amount)
        return amounts

    def update_clock(self, *args):
        self.app.clock_label.text = f"[size=26][b]{time.strftime('%I:%M %p %A %B %d, %Y')}[/b][/size]"
        self.app.clock_label.color = self.get_text_color()

    def update_lockscreen_clock(self, *args):

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
            price = item_info["price"]
            item_quantity = item_info["quantity"]
            item_total_price = item_info["total_price"]
            item_discount = item_info.get("discount", {"amount": 0, "percent": False})
            price_times_quantity = price * item_quantity

            if item_quantity > 1:
                if float(item_discount["amount"]) > 0:
                    item_display_text = f"{item_name}"
                    price_display_text = f"${price_times_quantity:.2f} - {float(item_discount['amount']):.2f}\n = ${item_total_price:.2f}"
                    quantity_display_text =  f"{item_quantity}"
                else:
                    item_display_text = f"{item_name}"
                    price_display_text = f"${item_total_price:.2f}"
                    quantity_display_text =  f"{item_quantity}"
            else:
                if float(item_discount["amount"]) > 0:
                    item_display_text = f"{item_name}"
                    price_display_text = f"${price_times_quantity:.2f} - {float(item_discount['amount']):.2f}\n = ${item_total_price:.2f}"
                    quantity_display_text =  ""
                else:
                    item_display_text = f"{item_name}"
                    price_display_text = f"${item_total_price:.2f}"
                    quantity_display_text =  ""

            blue_line = MDBoxLayout(size_hint_x=1, size_hint_y=None,height=1)
            blue_line.md_bg_color = (0.56, 0.56, 1, 1)
            blue_line2 = MDBoxLayout(size_hint_x=1, size_hint_y=None,height=1)
            blue_line2.md_bg_color = (0.56, 0.56, 1, 1)
            blue_line3 = MDBoxLayout(size_hint_x=1, size_hint_y=None,height=1)
            blue_line3.md_bg_color = (0.56, 0.56, 1, 1)
            item_layout = GridLayout(orientation='lr-tb', cols=3, rows=2, size_hint=(1,1))
            item_label_container = BoxLayout(size_hint_x=None, width=550)
            item_label = MDLabel(text=f"[size=20]{item_display_text}[/size]")
            item_label_container.add_widget(item_label)


            spacer = MDLabel(size_hint_x=1)
            #item_layout.add_widget(spacer)
            price_label_container = BoxLayout(size_hint_x=None, width=150)
            price_label = MDLabel(text=f"[size=20]{price_display_text}[/size]", halign="right")
            price_label_container.add_widget(price_label)

            quantity_label_container = BoxLayout(size_hint_x=None, width=50)
            quantity_label = MDLabel(text=f"[size=20]{quantity_display_text}[/size]")
            quantity_label_container.add_widget(quantity_label)

            item_layout.add_widget(item_label_container)
            item_layout.add_widget(quantity_label_container)
            item_layout.add_widget(price_label_container)
            item_layout.add_widget(blue_line)
            item_layout.add_widget(blue_line2)
            item_layout.add_widget(blue_line3)


            item_button = MDFlatButton(size_hint=(1,1))
            item_button.add_widget(item_layout)
            item_button.bind(on_press=lambda x, item_id=item_id: self.app.popup_manager.show_item_details_popup(item_id))

            self.app.order_layout.add_widget(item_button)
            # self.app.order_layout.add_widget(blue_line)

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

    def initialize_receipt_printer(self):
        self.app.receipt_printer = ReceiptPrinter(
            self.app,
            "receipt_printer_config.yaml"
            )

    def initialize_barcode_cache(self):

        all_items = self.app.db_manager.get_all_items()
        barcode_cache = {}
        #print(len(barcode_cache))
        for item in all_items:
            barcode = item[0]
            if barcode not in barcode_cache:
                barcode_cache[barcode] = {'items': [item], 'is_dupe': False}
            else:
                barcode_cache[barcode]['items'].append(item)
                barcode_cache[barcode]['is_dupe'] = True  # Mark as duplicate
        print(len(barcode_cache))
        return barcode_cache

    def initialize_invetory_cache(self):
        inventory = self.app.db_manager.get_all_items()
        return inventory

    def update_barcode_cache(self, item_details):
        barcode = item_details['barcode']
        if barcode not in self.app.barcode_cache:
            self.app.barcode_cache[barcode] = {'items': [item_details], 'is_dupe': False}
        else:
            self.app.barcode_cache[barcode]['items'].append(item_details)
            self.app.barcode_cache[barcode]['is_dupe'] = True

    def initialize_categories(self):
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
        # self.turn_on_monitor()

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

            #self.app.popup_manager.show_lock_screen()
            self.app.is_lock_screen_displayed = True
        elif (

            not self.app.is_guard_screen_displayed
            and not self.app.is_lock_screen_displayed
        ):

            #self.app.popup_manager.show_lock_screen()
            self.app.popup_manager.show_guard_screen()
            self.app.is_lock_screen_displayed = True
            self.app.is_guard_screen_displayed = True
        elif (
            self.app.is_lock_screen_displayed and not self.app.is_guard_screen_displayed
        ):

            self.app.popup_manager.show_guard_screen()
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
                self.app.theme_cls.primary_palette = settings.get(
                    "primary_palette", "Brown"
                )
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

            if idle_time > 600000:

                self.trigger_guard_and_lock(trigger=False)


        except Exception as e:
            #print(f"Exception in check_inactivity\n{e}")
            pass

    # def check_inactivity(self, *args):
    #     try:
    #         # Call xprintidle to get the idle time in milliseconds
    #         idle_time_output = subprocess.check_output(["xprintidle"]).decode().strip()
    #         idle_time = int(idle_time_output)
    #
    #         # Check if the idle time exceeds the threshold (600000 ms = 10 minutes)
    #         # if idle_time > 600000:
    #         if idle_time > 6000:
    #             print(idle_time, "if")
    #             self.trigger_guard_and_lock(trigger=False)
    #         print(idle_time)
    #
    #     except Exception as e:
    #         print(f"Exception in check_inactivity\n{e}")
    #         pass

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

        if (
            abs(self.app.popup_manager.split_payment_info["remaining_amount"])
            <= tolerance
        ):
            self.finalize_split_payment()
        else:
            self.app.popup_manager.show_split_payment_numeric_popup(
                subsequent_payment=True
            )

    def split_card_continue(self, amount, method):

        tolerance = 0.001
        self.app.popup_manager.dismiss_popups("split_card_confirm_popup")

        if (
            abs(self.app.popup_manager.split_payment_info["remaining_amount"])
            <= tolerance
        ):
            self.finalize_split_payment()
        else:
            self.app.popup_manager.show_split_payment_numeric_popup(
                subsequent_payment=True
            )

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
        Clock.schedule_once(
            lambda dt: setattr(layout, "background_color", original_color), 0.5
        )

    # elif instance.text == "TEST": TODO
    #     print("test button")
    #     eel_thread = threading.Thread(target=self.start_eel)
    #     eel_thread.daemon = True
    #     eel_thread.start()

    def dismiss_single_discount_popup(self):
        self.app.popup_manager.discount_item_popup.dismiss()
        self.app.popup_manager.item_popup.dismiss()
        try:
            self.app.popup_manager.discount_amount_input.text = ""
        except:
            pass
        try:
            self.app.popup_manager.discount_popup.dismiss()
        except:
            pass


    def dismiss_entire_discount_popup(self):
        try:
            self.app.popup_manager.custom_discount_order_amount_input.text = ""
        except:
            pass
        self.app.popup_manager.custom_discount_order_popup.dismiss()

    def dismiss_discount_order_popup(self):
        self.app.popup_manager.discount_order_popup.dismiss()
        self.app.financial_summary.order_mod_popup.dismiss()

    def update_confirm_and_close(
        self,
        barcode_input,
        name_input,
        price_input,
        cost_input,
        sku_input,
        category_input,
        popup,
    ):
        self.app.inventory_row.update_item_in_database(
            barcode_input,
            name_input,
            price_input,
            cost_input,
            sku_input,
            category_input,
        )
        self.app.inventory_manager.refresh_inventory()
        popup.dismiss()

    def inventory_item_confirm_and_close(
        self,
        barcode_input,
        name_input,
        price_input,
        cost_input,
        sku_input,
        category_input,
        popup,
    ):

        if len(name_input.text) > 0:

            self.app.inventory_manager.add_item_to_database(
                barcode_input,
                name_input,
                price_input,
                cost_input,
                sku_input,
                category_input,
            )
            self.app.inventory_manager.refresh_inventory()
            self.app.popup_manager.inventory_item_popup.dismiss()

    def set_generated_barcode(self, barcode_input):
        unique_barcode = self.generate_unique_barcode()
        self.app.popup_manager.barcode_input.text = unique_barcode

    def generate_unique_barcode(self):
        while True:
            new_barcode = str(
                upc_a(
                    str(random.randint(100000000000, 999999999999)), writer=None
                ).get_fullcode()
            )

            if not self.app.db_manager.barcode_exists(new_barcode):
                return new_barcode

    def apply_categories(self):
        categories_str = ", ".join(self.app.popup_manager.selected_categories)
        self.app.popup_manager.add_to_db_category_input.text = categories_str
        self.app.popup_manager.category_button_popup.dismiss()

    def apply_categories_inv(self):
        categories_str = ", ".join(
            self.app.popup_manager.selected_categories_inv
            )
        self.app.popup_manager.add_to_db_category_input_inv.text = categories_str
        self.app.popup_manager.category_button_popup_inv.dismiss()

    def apply_categories_row(self):
        categories_str = ", ".join(
            self.app.popup_manager.selected_categories_row
            )
        self.app.popup_manager.add_to_db_category_input_row.text = categories_str
        self.app.popup_manager.category_button_popup_row.dismiss()

    def toggle_category_selection(self, is_active, category):
        if is_active:
            if category not in self.app.popup_manager.selected_categories:
                self.app.popup_manager.selected_categories.append(category)
        else:
            if category in self.app.popup_manager.selected_categories:
                self.app.popup_manager.selected_categories.remove(category)

    def toggle_category_selection_row(self, is_active, category):
        if is_active:
            if category not in self.app.popup_manager.selected_categories_row:
                self.app.popup_manager.selected_categories_row.append(category)

        else:
            if category in self.app.popup_manager.selected_categories_row:
                self.app.popup_manager.selected_categories_row.append(category)

    def toggle_category_selection_inv(self, is_active, category):
        if is_active:
            if category not in self.app.popup_manager.selected_categories_inv:
                self.app.popup_manager.selected_categories_inv.append(category)

        else:
            if category in self.app.popup_manager.selected_categories_inv:
                self.app.popup_manager.selected_categories_inv.append(category)


    def show_add_item_popup(self, scanned_barcode):
        self.barcode = scanned_barcode
        self.app.popup_manager.inventory_item_popup()



    def open_inventory_manager_row(self, instance):
        self.app.current_context = "inventory_item"
        self.app.popup_manager.inventory_item_popup_row(instance)

    def update_apply_categories(self):
        categories_str = ", ".join(self.update_selected_categories)
        self.update_category_input.text = categories_str
        self.update_category_button_popup.dismiss()

    def update_toggle_category_selection(self, instance, category):
        if category in self.update_selected_categories:
            self.update_selected_categories.remove(category)
            instance.text = category
        else:
            self.update_selected_categories.append(category)
            instance.text = f"{category}\n (Selected)"


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



# class CustomTextInput(TextInput):
#     def __init__(self, ref=None, **kwargs):
#         super(CustomTextInput, self).__init__(**kwargs)
#         self.bind(focus=self.on_focus)
#         self.app = ref
#         self._keyboard = None
#
#     def on_focus(self, instance, value):
#         if value:
#             self.request_keyboard()
#         else:
#             if self._keyboard is not None:
#                 self.release_keyboard()
#
#     def request_keyboard(self):
#         if self._keyboard is None:
#             self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
#             self._keyboard.bind(on_key_down=self._on_keyboard_down)
#
#
#
#         if hasattr(self._keyboard, 'widget') and self._keyboard.widget:
#             vkeyboard = self._keyboard.widget
#             vkeyboard.docked = False
#             vkeyboard.pos = (100, 100)
#
#     def release_keyboard(self):
#         if self._keyboard is not None:
#             self._keyboard.unbind(on_key_down=self._on_keyboard_down)
#             self._keyboard.release()
#             self._keyboard = None
#
#
#     def _keyboard_closed(self):
#
#         self.release_keyboard()
#
#     def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
#
#
#         pass
