from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ProductCategory:
    name: str
    group: str


class ProductCategoryStore:

    _DEFAULT_COMMON = [
        "American Glass Bongs",
        "American Glass Pipes",
        "American Glass Bubblers",
        "American Glass Rigs",
        "American Glass Slides",
        "Import Glass Bongs",
        "Import Glass Pipes",
        "Import Glass Bubblers",
        "Import Glass Rigs",
        "Import Glass Slides",
        "Shitty Import Quartz",
        "Fancy Import Quartz",
        "American Quartz",
        "Import Chillums",
        "American Chillums",
        "Grinders",
        "510 Batteries",
        "Concentrate Vapes",
        "Dry Vapes",
        "Silicone",
        "Cleaners",
        "Butane",
        "Downstems",
        "Wraps",
    ]

    _DEFAULT_UNCOMMON = [
        "Rolling papers",
        "Cigarettes",
        "Cigars",
        "Pouches (zyn, etc)",
        "Nicotine Vapes",
        "Torches",
        "Lighters",
        "THC",
        "CBD",
        "Dugouts",
        "Trays/Ashtrays",
        "Jewelry",
        "Other Accessories",
        "Everything Else",
    ]

    def __init__(self):
        self._categories: Dict[str, ProductCategory] = {}
        self._seed_defaults()

    def _seed_defaults(self):
        for name in self._DEFAULT_COMMON:
            self.create(name, "common")
        for name in self._DEFAULT_UNCOMMON:
            self.create(name, "uncommon")

    def create(self, name: str, group: str = "common") -> ProductCategory:
        key = (name or "").strip()
        if not key:
            raise ValueError("Category name is required")
        normalized_group = "uncommon" if group == "uncommon" else "common"
        category = ProductCategory(name=key, group=normalized_group)
        self._categories[key.lower()] = category
        return category

    def read(self, name: str):
        key = (name or "").strip().lower()
        return self._categories.get(key)

    def update(self, existing_name: str, new_name: str = None, group: str = None):
        current = self.read(existing_name)
        if not current:
            return None

        updated_name = (new_name or current.name).strip()
        updated_group = group if group in ("common", "uncommon") else current.group

        del self._categories[current.name.lower()]
        updated = ProductCategory(name=updated_name, group=updated_group)
        self._categories[updated.name.lower()] = updated
        return updated

    def delete(self, name: str) -> bool:
        key = (name or "").strip().lower()
        if key in self._categories:
            del self._categories[key]
            return True
        return False

    def list_all(self) -> List[str]:
        common = self.list_by_group("common")
        uncommon = self.list_by_group("uncommon")
        return common + uncommon

    def list_by_group(self, group: str) -> List[str]:
        normalized_group = "uncommon" if group == "uncommon" else "common"
        return [c.name for c in self._categories.values() if c.group == normalized_group]
