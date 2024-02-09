import json
from kivymd.uix.button import MDRaisedButton
import time
import subprocess
import re
import threading

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
        self.app.popup_manager.category_button_popup.dismiss()

    def reset_pin_timer(self):
        if self.app.pin_reset_timer is not None:
            self.app.pin_reset_timer.cancel()

        self.app.pin_reset_timer = threading.Timer(5.0, self.reset_pin)
        self.app.pin_reset_timer.start()

    def reset_pin(self):
        self.app.entered_pin = ""

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
                on_press=lambda x: self.app.popup_manager.show_item_details_popup(item_id)
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
        if current_time - self.override_tap_time < 1:
            sys.exit(42)
        else:
            self.override_tap_time = current_time

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
            self.popup_manager.show_custom_item_popup(barcode)
        elif choice_text == "Add to Database":
            self.popup_manager.show_add_to_database_popup(barcode)

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
        self.turn_on_monitor()

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



    def check_monitor_status(self, dt):
        if self.is_monitor_off():
            if not self.app.is_guard_screen_displayed and not self.app.is_lock_screen_displayed:
                self.app.popup_manager.show_lock_screen()
                self.app.popup_manager.show_guard_screen()
        else:
            self.app.is_guard_screen_displayed = False
            self.app.is_lock_screen_displayed = False

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
                self.app.theme_cls.primary_palette = settings.get(
                    "primary_palette", "Brown"
                )
                self.app.theme_cls.theme_style = settings.get("theme_style", "Light")
        except FileNotFoundError as e:
            print(e)

    def turn_off_monitor(self):
        touchscreen_device = "iSolution multitouch"
        try:
            subprocess.run(["xinput", "disable", touchscreen_device], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            subprocess.run(["xinput", "enable", touchscreen_device], check=True)
            return

        try:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "0"], check=True
            )
        except subprocess.CalledProcessError as e:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "1"], check=True
            )
            print(e)
            return

        def reenable_touchscreen():
            time.sleep(1)
            try:
                subprocess.run(["xinput", "enable", touchscreen_device], check=True)
            except subprocess.CalledProcessError as e:
                print(e)

        threading.Thread(target=reenable_touchscreen).start()

    def is_monitor_off(self):
        output_name = "HDMI-1"
        try:
            result = subprocess.run(
                ["xrandr", "--verbose"], stdout=subprocess.PIPE, check=True
            )
            output = result.stdout.decode("utf-8")
            pattern = rf"{output_name} connected.*?Brightness: (\d+\.\d+)"
            match = re.search(pattern, output, re.DOTALL)

            if match:
                current_brightness = float(match.group(1))
                return current_brightness == 0.0
            else:
                return False
        except Exception as e:
            print(e)
            return False

    def turn_on_monitor(self):
        try:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "1"], check=True
            )
        except Exception as e:
            print(e)



    def _test_current_context(self):
        while True:
            print(self.current_context)
            time.sleep(1)

    def _test_current_context_thread(self):
        test_thread = threading.Thread(target=self._test_current_context)
        test_thread.daemon = True
        test_thread.start()

    def check_inactivity(self, *args):
        try:

            result = subprocess.run(["xprintidle"], stdout=subprocess.PIPE, check=True)
            inactive_time = int(result.stdout.decode().strip())

            if inactive_time > 600000:
                self.turn_off_monitor()

        except Exception as e:
            print(e)
