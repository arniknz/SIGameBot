from __future__ import annotations

import dataclasses

import game.constants

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
    category: game.constants.ShopCategory
    effect: game.constants.ItemEffect


SHOP_ITEMS: tuple[ShopItemDef, ...] = (
    ShopItemDef(
        1,
        "🗡️",
        "Двойной клинок",
        "x2 очка за верный ответ",
        500,
        game.constants.ShopCategory.WEAPONS,
        game.constants.ItemEffect.DOUBLE_POINTS,
    ),
    ShopItemDef(
        2,
        "🛡️",
        "Щит",
        "Нет штрафа за неверный ответ",
        400,
        game.constants.ShopCategory.WEAPONS,
        game.constants.ItemEffect.NO_PENALTY,
    ),
    ShopItemDef(
        3,
        "🏹",
        "Стрела времени",
        f"+{EXTRA_TIME_SECONDS} сек на ответ",
        300,
        game.constants.ShopCategory.WEAPONS,
        game.constants.ItemEffect.EXTRA_TIME,
    ),
    ShopItemDef(
        4,
        "🔮",
        "Хрустальный шар",
        "Показывает подсказку к ответу",
        200,
        game.constants.ShopCategory.WEAPONS,
        game.constants.ItemEffect.REVEAL_HINT,
    ),
    ShopItemDef(
        8,
        "💎",
        "Алмаз",
        "Любой ответ засчитывается как верный",
        1000,
        game.constants.ShopCategory.SCROLLS,
        game.constants.ItemEffect.FORCE_CORRECT,
    ),
    ShopItemDef(
        9,
        "🃏",
        "Джокер",
        "Заменяет текущий вопрос на другой",
        600,
        game.constants.ShopCategory.ILLUSIONS,
        game.constants.ItemEffect.REPLACE_QUESTION,
    ),
    ShopItemDef(
        10,
        "🪞",
        "Зеркало",
        "Штраф переводится на случайного соперника",
        800,
        game.constants.ShopCategory.ILLUSIONS,
        game.constants.ItemEffect.TRANSFER_PENALTY,
    ),
    ShopItemDef(
        11,
        "⏳",
        "Песочные часы",
        "Возвращает случайный отыгранный вопрос на табло",
        1000,
        game.constants.ShopCategory.ILLUSIONS,
        game.constants.ItemEffect.RESURRECT_QUESTION,
    ),
    ShopItemDef(
        13,
        "👑",
        "Корона",
        f"+{BONUS_START_POINTS} очков сразу",
        800,
        game.constants.ShopCategory.TITLES,
        game.constants.ItemEffect.BONUS_POINTS,
    ),
    ShopItemDef(
        16,
        "💍",
        "Кольцо власти",
        "Вы выбираете следующий вопрос",
        1200,
        game.constants.ShopCategory.TITLES,
        game.constants.ItemEffect.BECOME_CHOOSER,
    ),
)

ITEMS_BY_ID: dict[int, ShopItemDef] = {item.id: item for item in SHOP_ITEMS}

ITEMS_BY_CATEGORY: dict[game.constants.ShopCategory, list[ShopItemDef]] = {}
for _item in SHOP_ITEMS:
    ITEMS_BY_CATEGORY.setdefault(_item.category, []).append(_item)

CATEGORY_LABELS: dict[game.constants.ShopCategory, str] = {
    game.constants.ShopCategory.WEAPONS: "⚔️ Оружие",
    game.constants.ShopCategory.SCROLLS: "📜 Свитки",
    game.constants.ShopCategory.ILLUSIONS: "🌀 Иллюзии",
    game.constants.ShopCategory.TITLES: "🏅 Титулы",
}
