from __future__ import annotations

import re
from enum import StrEnum

from ecommerce.domain.errors import InvalidValue


class Category(StrEnum):
    ACCESSORIES = "accessories"
    BEAUTY = "beauty"
    BOOKS = "books"
    CLOTHING = "clothing"
    ELECTRONICS = "electronics"
    FOOD_AND_BEVERAGE = "food-beverage"
    FOOTWEAR = "footwear"
    GAMES = "games"
    GIFTS = "gifts"
    HEALTH = "health"
    HOME_AND_OFFICE = "home-office"
    KITCHEN = "kitchen"
    MISC = "misc"
    OUTDOORS = "outdoors"
    PETS = "pets"
    SPORTS = "sports"
    STATIONERY = "stationery"
    TOOLS = "tools"

    @property
    def label(self) -> str:
        return _LABELS[self]

    @classmethod
    def parse(cls, raw: str) -> Category:
        key = _lookup_key(raw)
        if not key:
            raise InvalidValue("is required")
        category = _BY_KEY.get(key)
        if category is None:
            raise InvalidValue(f"'{raw.strip()}' is not a known category")
        return category


_LABELS: dict[Category, str] = {
    Category.ACCESSORIES: "Accessories",
    Category.BEAUTY: "Beauty",
    Category.BOOKS: "Books",
    Category.CLOTHING: "Clothing",
    Category.ELECTRONICS: "Electronics",
    Category.FOOD_AND_BEVERAGE: "Food & Beverage",
    Category.FOOTWEAR: "Footwear",
    Category.GAMES: "Games",
    Category.GIFTS: "Gifts",
    Category.HEALTH: "Health",
    Category.HOME_AND_OFFICE: "Home & Office",
    Category.KITCHEN: "Kitchen",
    Category.MISC: "Misc",
    Category.OUTDOORS: "Outdoors",
    Category.PETS: "Pets",
    Category.SPORTS: "Sports",
    Category.STATIONERY: "Stationery",
    Category.TOOLS: "Tools",
}


def _lookup_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", raw.casefold().replace("&", "and"))


_BY_KEY: dict[str, Category] = {
    **{_lookup_key(category.value): category for category in Category},
    **{_lookup_key(label): category for category, label in _LABELS.items()},
}
