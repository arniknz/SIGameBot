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
        "Двойной клинок",
        "x2 очка за верный ответ",
        500,
        ShopCategory.WEAPONS,
        ItemEffect.DOUBLE_POINTS,
    ),
    ShopItemDef(
        2,
        "🛡️",
        "Щит",
        "Нет штрафа за неверный ответ",
        400,
        ShopCategory.WEAPONS,
        ItemEffect.NO_PENALTY,
    ),
    ShopItemDef(
        3,
        "🏹",
        "Стрела времени",
        f"+{EXTRA_TIME_SECONDS} сек на ответ",
        300,
        ShopCategory.WEAPONS,
        ItemEffect.EXTRA_TIME,
    ),
    ShopItemDef(
        4,
        "🔮",
        "Хрустальный шар",
        "Показывает подсказку к ответу",
        200,
        ShopCategory.WEAPONS,
        ItemEffect.REVEAL_HINT,
    ),
    ShopItemDef(
        5,
        "📖",
        "Древний свиток",
        "Показывает правильный ответ",
        600,
        ShopCategory.SCROLLS,
        ItemEffect.REVEAL_ANSWER,
    ),
    ShopItemDef(
        6,
        "⚡",
        "Молния",
        "Автоматически нажимает звонок на следующий вопрос",
        800,
        ShopCategory.SCROLLS,
        ItemEffect.AUTO_BUZZER,
    ),
    ShopItemDef(
        7,
        "💀",
        "Пасс смерти",
        "При неверном ответе вопрос возвращается на табло",
        700,
        ShopCategory.SCROLLS,
        ItemEffect.PASS_ON_WRONG,
    ),
    ShopItemDef(
        8,
        "💎",
        "Алмаз",
        "Любой ответ засчитывается как верный",
        1000,
        ShopCategory.SCROLLS,
        ItemEffect.FORCE_CORRECT,
    ),
    ShopItemDef(
        9,
        "🃏",
        "Джокер",
        "Заменяет текущий вопрос на другой",
        600,
        ShopCategory.ILLUSIONS,
        ItemEffect.REPLACE_QUESTION,
    ),
    ShopItemDef(
        10,
        "🪞",
        "Зеркало",
        "Штраф переводится на случайного соперника",
        800,
        ShopCategory.ILLUSIONS,
        ItemEffect.TRANSFER_PENALTY,
    ),
    ShopItemDef(
        11,
        "⏳",
        "Песочные часы",
        "Возвращает случайный отыгранный вопрос на табло",
        1000,
        ShopCategory.ILLUSIONS,
        ItemEffect.RESURRECT_QUESTION,
    ),
    ShopItemDef(
        12,
        "📦",
        "Ящик Пандоры",
        "Сразу открывает случайный новый вопрос",
        1200,
        ShopCategory.ILLUSIONS,
        ItemEffect.OPEN_ANY,
    ),
    ShopItemDef(
        13,
        "👑",
        "Корона",
        f"+{BONUS_START_POINTS} очков сразу",
        800,
        ShopCategory.TITLES,
        ItemEffect.BONUS_POINTS,
    ),
    ShopItemDef(
        14,
        "🧥",
        "Плащ",
        "Скрывает ваш счёт на табло",
        600,
        ShopCategory.TITLES,
        ItemEffect.HIDE_SCORE,
    ),
    ShopItemDef(
        15,
        "🧌",
        "Тролль",
        f"Крадёт {STEAL_AMOUNT} очков у соперника",
        900,
        ShopCategory.TITLES,
        ItemEffect.STEAL_POINTS,
    ),
    ShopItemDef(
        16,
        "💍",
        "Кольцо власти",
        "Вы выбираете следующий вопрос",
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
    ShopCategory.WEAPONS: "⚔️ Оружие",
    ShopCategory.SCROLLS: "📜 Свитки",
    ShopCategory.ILLUSIONS: "🌀 Иллюзии",
    ShopCategory.TITLES: "🏅 Титулы",
}
