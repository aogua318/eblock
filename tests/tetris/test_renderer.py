"""renderer 模块测试（实施指南 M3）。

覆盖:
    - 默认 GameState 与构造的 HighScore 调用 draw 不抛异常；
    - paused / game_over 覆盖层分别绘制不抛异常。
"""

import os

# 必须在 import pygame 之前设置 dummy 驱动（无显示器环境）。
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from eblock.tetris.config import load_default_config
from eblock.tetris.save.highscore import HighScore
from eblock.tetris.sim.game import Game, GameState
from eblock.tetris.ui.renderer import Renderer

WIDTH = 560
HEIGHT = 640


def _new_renderer() -> Renderer:
    """创建 560×640 表面与默认配置的渲染器。"""
    screen = pygame.Surface((WIDTH, HEIGHT))
    return Renderer(screen, load_default_config())


def _default_state() -> GameState:
    """新对局的默认快照。"""
    return Game(load_default_config(), seed=0).to_state()


def test_draw_does_not_raise() -> None:
    """对默认 GameState 与构造的 HighScore 调用 draw 不抛异常。"""
    renderer = _new_renderer()
    highscore = HighScore(score=100, level=1, lines=0, date="2026-08-15")
    renderer.draw(_default_state(), highscore, paused=False, game_over=False)


def test_draw_paused_and_game_over_overlays() -> None:
    """paused / game_over 覆盖层分别绘制不抛异常。"""
    renderer = _new_renderer()
    highscore = HighScore(score=100, level=1, lines=0, date="2026-08-15")
    renderer.draw(_default_state(), highscore, paused=True, game_over=False)
    renderer.draw(_default_state(), highscore, paused=False, game_over=True)
