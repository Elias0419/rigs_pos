import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


_CATEGORY_DATA_FILE = Path(
    os.environ.get("RIGS_PRODUCT_CATEGORIES_PATH", Path(__file__).with_name("product_categories.json"))
)


@dataclass(frozen=True)
class ProductCategory:
    id: str
    name: str
    group: str

    @classmethod
    def from_dict(cls, data: dict) -> "ProductCategory":
        return cls(
            id=_normalize_id(data.get("id") or data.get("name")),
            name=_normalize_name(data.get("name")),
            group=_normalize_group(data.get("group")),
        )

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "group": self.group}


def _normalize_name(name: str) -> str:
    normalized = (name or "").strip()
    if not normalized:
        raise ValueError("Category name is required")
    return normalized


def _normalize_group(group: str) -> str:
    return "uncommon" if group == "uncommon" else "common"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "category"


def _normalize_id(category_id: str) -> str:
    normalized = _slugify(category_id)
    if not normalized:
        raise ValueError("Category id is required")
    return normalized


class ProductCategoryStore:
    """Loads and manages product categories.

    Categories are identified by stable ids, while existing callers can continue
    to read and persist category names. That keeps historical transaction and
    item data intact until a later migration chooses to store ids directly.
    """

    data_file = _CATEGORY_DATA_FILE

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = Path(data_file) if data_file is not None else self.data_file
        self._categories: Dict[str, ProductCategory] = {}
        self._name_index: Dict[str, str] = {}
        self._load_defaults()

    def _load_defaults(self):
        if self.data_file.exists():
            self._load_json(self.data_file)
        else:
            self._seed_defaults()

    def _load_json(self, data_file: Path):
        with data_file.open("r", encoding="utf-8") as category_file:
            data = json.load(category_file)

        for item in data.get("categories", []):
            self._add(ProductCategory.from_dict(item))

    def _seed_defaults(self):
        # Kept as a fallback for development/test environments where the data
        # file is unavailable. The authoritative defaults live in JSON.
        for item in DEFAULT_CATEGORY_DATA["categories"]:
            self._add(ProductCategory.from_dict(item))

    def _add(self, category: ProductCategory):
        if category.id in self._categories:
            raise ValueError(f"Duplicate category id: {category.id}")

        name_key = category.name.lower()
        if name_key in self._name_index:
            raise ValueError(f"Duplicate category name: {category.name}")

        self._categories[category.id] = category
        self._name_index[name_key] = category.id
        return category

    def create(
        self, name: str, group: str = "common", category_id: Optional[str] = None
    ) -> ProductCategory:
        category = ProductCategory(
            id=_normalize_id(category_id or name),
            name=_normalize_name(name),
            group=_normalize_group(group),
        )
        return self._add(category)

    def read(self, name_or_id: str):
        key = (name_or_id or "").strip()
        if not key:
            return None

        category = self._categories.get(_normalize_id(key))
        if category:
            return category

        category_id = self._name_index.get(key.lower())
        return self._categories.get(category_id) if category_id else None

    def update(
        self,
        existing_name_or_id: str,
        new_name: str = None,
        group: str = None,
        category_id: str = None,
    ):
        current = self.read(existing_name_or_id)
        if not current:
            return None

        updated = ProductCategory(
            id=_normalize_id(category_id or current.id),
            name=_normalize_name(new_name or current.name),
            group=_normalize_group(group) if group is not None else current.group,
        )

        if updated.id != current.id and updated.id in self._categories:
            raise ValueError(f"Duplicate category id: {updated.id}")

        updated_name_key = updated.name.lower()
        existing_id_for_name = self._name_index.get(updated_name_key)
        if existing_id_for_name and existing_id_for_name != current.id:
            raise ValueError(f"Duplicate category name: {updated.name}")

        del self._categories[current.id]
        del self._name_index[current.name.lower()]
        self._categories[updated.id] = updated
        self._name_index[updated_name_key] = updated.id
        return updated

    def delete(self, name_or_id: str) -> bool:
        category = self.read(name_or_id)
        if not category:
            return False

        del self._categories[category.id]
        del self._name_index[category.name.lower()]
        return True

    def list_all(self) -> List[str]:
        common = self.list_by_group("common")
        uncommon = self.list_by_group("uncommon")
        return common + uncommon

    def list_by_group(self, group: str) -> List[str]:
        normalized_group = _normalize_group(group)
        return [c.name for c in self._categories.values() if c.group == normalized_group]

    def list_category_objects(self) -> List[ProductCategory]:
        return list(self._categories.values())

    def to_dict(self) -> dict:
        return {"categories": [c.to_dict() for c in self.list_category_objects()]}

    def save(self):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as category_file:
            json.dump(self.to_dict(), category_file, indent=2)
            category_file.write("\n")


DEFAULT_CATEGORY_DATA = {
    "categories": [
        {"id": "american-glass-bongs", "name": "American Glass Bongs", "group": "common"},
        {"id": "american-glass-pipes", "name": "American Glass Pipes", "group": "common"},
        {"id": "american-glass-bubblers", "name": "American Glass Bubblers", "group": "common"},
        {"id": "american-glass-rigs", "name": "American Glass Rigs", "group": "common"},
        {"id": "american-glass-slides", "name": "American Glass Slides", "group": "common"},
        {"id": "import-glass-bongs", "name": "Import Glass Bongs", "group": "common"},
        {"id": "import-glass-pipes", "name": "Import Glass Pipes", "group": "common"},
        {"id": "import-glass-bubblers", "name": "Import Glass Bubblers", "group": "common"},
        {"id": "import-glass-rigs", "name": "Import Glass Rigs", "group": "common"},
        {"id": "import-glass-slides", "name": "Import Glass Slides", "group": "common"},
        {"id": "shitty-import-quartz", "name": "Shitty Import Quartz", "group": "common"},
        {"id": "fancy-import-quartz", "name": "Fancy Import Quartz", "group": "common"},
        {"id": "american-quartz", "name": "American Quartz", "group": "common"},
        {"id": "import-chillums", "name": "Import Chillums", "group": "common"},
        {"id": "american-chillums", "name": "American Chillums", "group": "common"},
        {"id": "grinders", "name": "Grinders", "group": "common"},
        {"id": "510-batteries", "name": "510 Batteries", "group": "common"},
        {"id": "concentrate-vapes", "name": "Concentrate Vapes", "group": "common"},
        {"id": "dry-vapes", "name": "Dry Vapes", "group": "common"},
        {"id": "silicone", "name": "Silicone", "group": "common"},
        {"id": "cleaners", "name": "Cleaners", "group": "common"},
        {"id": "butane", "name": "Butane", "group": "common"},
        {"id": "downstems", "name": "Downstems", "group": "common"},
        {"id": "wraps", "name": "Wraps", "group": "common"},
        {"id": "rolling-papers", "name": "Rolling papers", "group": "uncommon"},
        {"id": "cigarettes", "name": "Cigarettes", "group": "uncommon"},
        {"id": "cigars", "name": "Cigars", "group": "uncommon"},
        {"id": "tobacco", "name": "Tobacco", "group": "uncommon"},
        {"id": "pouches-zyn-etc", "name": "Pouches (zyn, etc)", "group": "uncommon"},
        {"id": "nicotine-vapes", "name": "Nicotine Vapes", "group": "uncommon"},
        {"id": "torches", "name": "Torches", "group": "uncommon"},
        {"id": "lighters", "name": "Lighters", "group": "uncommon"},
        {"id": "thc", "name": "THC", "group": "uncommon"},
        {"id": "cbd", "name": "CBD", "group": "uncommon"},
        {"id": "dugouts", "name": "Dugouts", "group": "uncommon"},
        {"id": "trays-ashtrays", "name": "Trays/Ashtrays", "group": "uncommon"},
        {"id": "jewelry", "name": "Jewelry", "group": "uncommon"},
        {"id": "carb-caps", "name": "Carb Caps", "group": "uncommon"},
        {"id": "dab-tools", "name": "Dab Tools", "group": "uncommon"},
        {"id": "other-accessories", "name": "Other Accessories", "group": "uncommon"},
        {"id": "everything-else", "name": "Everything Else", "group": "uncommon"}
    ]
}
