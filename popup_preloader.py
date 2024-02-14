from popups import PopupManager

class PopupPreloader:
    def __init__(self, ref):
        self.app = ref
        self.category_popup = self.app.popup_manager.create_category_popup()
        self.add_or_bypass_popup = self.app.popup_manager.show_add_or_bypass_popup()

    def update_and_show_add_or_bypass_popup(self, barcode):
        self.app.popup_manager.barcode_label.text = f"Barcode: {barcode}"
        self.add_or_bypass_popup.open()
