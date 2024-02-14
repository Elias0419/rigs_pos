from popups import PopupManager

class PopupPreloader:
    def __init__(self, ref):
        self.app = ref

        self.category_popup = self.app.popup_manager.create_category_popup()
        #self.add_or_bypass_popup = self.app.popup_manager.show_add_or_bypass_popup()
        self.single_item_discount_popup = self.app.popup_manager.add_discount_popup()
        self.entire_order_discount_popup = self.app.popup_manager.add_order_discount_popup()
        #self.label_printing_popup = self.app.popup_manager.show_label_printing_view()
        #self.inventory_management_view_popup = self.app.popup_manager.show_inventory_management_view()
        self.adjust_price_popup = self.app.popup_manager.show_adjust_price_popup()
        self.guard_popup = self.app.popup_manager.show_guard_screen()
        self.lock_popup = self.app.popup_manager.show_lock_screen()
        #self.inventory_search_popup = self.app.popup_manager.show_inventory()
        self.tools_popup = self.app.popup_manager.show_tools_popup()
        self.custom_item_popup = self.app.popup_manager.show_custom_item_popup()


    def update_and_show_add_or_bypass_popup(self, barcode):
        self.app.popup_manager.barcode_label.text = f"Barcode: {barcode}"
        self.add_or_bypass_popup.open()
