from __future__ import annotations

import dataclasses

from game.constants import ItemEffect, ShopCategory

EXTRA_TIME_SECONDS = 5
BONUS_START_POINTS = 100
STEAL_AMOUNT = 50


@dataclasses.dataclass(frozen=True)
class ShopItemDef:
    id: int
    emoji: str
    name: str
    description: str
    price: int
    category: ShopCategory
    effect: ItemEffect


SHOP_ITEMS: tuple[ShopItemDef, ...] = (
    ShopItemDef(
        1,
        "🗡️",
        "Double Blade",
        "x2 points for correct answer",
        500,
        ShopCategory.WEAPONS,
        ItemEffect.DOUBLE_POINTS,
    ),
    ShopItemDef(
        2,
        "🛡️",
        "Shield",
        "No penalty for wrong answer",
        400,
        ShopCategory.WEAPONS,
        ItemEffect.NO_PENALTY,
    ),
    ShopItemDef(
        3,
        "🏹",
        "Time Arrow",
        f"+{EXTRA_TIME_SECONDS} seconds to answer",
        300,
        ShopCategory.WEAPONS,
        ItemEffect.EXTRA_TIME,
    ),
    ShopItemDef(
        4,
        "🔮",
        "Crystal Ball",
        "Reveals a hint about the answer",
        200,
        ShopCategory.WEAPONS,
        ItemEffect.REVEAL_HINT,
    ),
    ShopItemDef(
        5,
        "📖",
        "Ancient Scroll",
        "Shows the correct answer",
        600,
        ShopCategory.SCROLLS,
        ItemEffect.REVEAL_ANSWER,
    ),
    ShopItemDef(
        6,
        "⚡",
        "Lightning",
        "Auto-buzz the next question",
        800,
        ShopCategory.SCROLLS,
        ItemEffect.AUTO_BUZZER,
    ),
    ShopItemDef(
        7,
        "💀",
        "Death Pass",
        "Wrong answer returns question to board",
        700,
        ShopCategory.SCROLLS,
        ItemEffect.PASS_ON_WRONG,
    ),
    ShopItemDef(
        8,
        "💎",
        "Diamond",
        "Treats any answer as correct",
        1000,
        ShopCategory.SCROLLS,
        ItemEffect.FORCE_CORRECT,
    ),
    ShopItemDef(
        9,
        "🃏",
        "Joker",
        "Replaces current question with another",
        600,
        ShopCategory.ILLUSIONS,
        ItemEffect.REPLACE_QUESTION,
    ),
    ShopItemDef(
        10,
        "🪞",
        "Mirror",
        "Penalty transfers to a random opponent",
        800,
        ShopCategory.ILLUSIONS,
        ItemEffect.TRANSFER_PENALTY,
    ),
    ShopItemDef(
        11,
        "⏳",
        "Hourglass",
        "Resurrects a random answered question",
        1000,
        ShopCategory.ILLUSIONS,
        ItemEffect.RESURRECT_QUESTION,
    ),
    ShopItemDef(
        12,
        "📦",
        "Pandora's Box",
        "Opens a random new question immediately",
        1200,
        ShopCategory.ILLUSIONS,
        ItemEffect.OPEN_ANY,
    ),
    ShopItemDef(
        13,
        "👑",
        "Crown",
        f"+{BONUS_START_POINTS} points immediately",
        800,
        ShopCategory.TITLES,
        ItemEffect.BONUS_POINTS,
    ),
    ShopItemDef(
        14,
        "🧥",
        "Cloak",
        "Hides your score from the board",
        600,
        ShopCategory.TITLES,
        ItemEffect.HIDE_SCORE,
    ),
    ShopItemDef(
        15,
        "🧌",
        "Troll",
        f"Steals {STEAL_AMOUNT} points from an opponent",
        900,
        ShopCategory.TITLES,
        ItemEffect.STEAL_POINTS,
    ),
    ShopItemDef(
        16,
        "💍",
        "Ring of Power",
        "You choose the next question",
        1200,
        ShopCategory.TITLES,
        ItemEffect.BECOME_CHOOSER,
    ),
)

ITEMS_BY_ID: dict[int, ShopItemDef] = {item.id: item for item in SHOP_ITEMS}

ITEMS_BY_CATEGORY: dict[ShopCategory, list[ShopItemDef]] = {}
for _item in SHOP_ITEMS:
    ITEMS_BY_CATEGORY.setdefault(_item.category, []).append(_item)

CATEGORY_LABELS: dict[ShopCategory, str] = {
    ShopCategory.WEAPONS: "⚔️ Weapons",
    ShopCategory.SCROLLS: "📜 Scrolls",
    ShopCategory.ILLUSIONS: "🌀 Illusions",
    ShopCategory.TITLES: "🏅 Titles",
}
