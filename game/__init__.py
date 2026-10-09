"""SeaWarAi: морской бой против ИИ, который считает вероятности и не подглядывает.

Вход игры по контракту PythonAiGames: GAME_INFO и create_widget(ctx). Qt загружается
только в create_widget - правила и ИИ работают без него.
"""
from game.version import VERSION

GAME_INFO = {
    "id": "seawar",
    "title": {"ru": "Морской бой", "en": "Sea Battle"},
    "summary": {"ru": "Морской бой против ИИ с картой вероятностей, который не видит ваших кораблей",
                "en": "Sea battle against a probability-map AI that never sees your ships"},
    "preview": "docs/preview.png",
    "version": VERSION,
}

APP_NAME = "SeaWarAi"


def create_widget(ctx):
    """ctx: aikit.Context. Виджет с меню, расстановкой, боем, статистикой и настройками."""
    from game.ui.widget import GameWidget
    return GameWidget(ctx)
