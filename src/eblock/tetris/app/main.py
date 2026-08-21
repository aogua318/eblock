"""俄罗斯方块装配与主循环（M3）。

职责：把 config / sim / ui / save 组装成可玩的窗口程序：
  输入 → sim.step → 渲染 → 高分保存，并处理暂停/重开/退出。
依赖方向：app 位于最上层，只做装配与流程编排，不包含游戏规则。
"""

import pygame

from eblock.tetris.config import load_default_config
from eblock.tetris.save.highscore import HighscoreStore, mode_key
from eblock.tetris.sim.game import Game, GameEvent
from eblock.tetris.ui.input import DEFAULT_KEYMAP, InputController
from eblock.tetris.ui.renderer import Renderer

# 窗口尺寸与帧率（文档 §7.1 / §5.4）。
WINDOW_WIDTH = 560
WINDOW_HEIGHT = 640
FPS = 60


def main() -> int:
    """运行俄罗斯方块主循环。

    参数:
        无。

    返回:
        退出码；正常退出返回 0。

    实现流程（严格按文档 §5.4）:
        1. 初始化与建窗：
           - pygame.init()；
           - 创建约 560×640 窗口，标题 “eblock - Tetris”；
           - pygame.time.Clock() 控制帧率。
           实现时需要 `import pygame`。
        2. 装配各层：
           - config = load_default_config()；
           - game = Game(config)；
           - input_controller = InputController(config.input.das_ms, config.input.arr_ms)；
           - renderer = Renderer(screen, config)；
           - store = HighscoreStore()（构造时自动加载磁盘纪录）。
           实现时需要导入：
             from eblock.tetris.config import load_default_config
             from eblock.tetris.sim.game import Game
             from eblock.tetris.ui.input import InputController
             from eblock.tetris.ui.renderer import Renderer
             from eblock.tetris.save.highscore import HighscoreStore, mode_key
        3. 每帧：dt_ms = clock.tick(60)（封顶 60 FPS）。
        4. 事件处理（不传给 sim 的）：
           - QUIT → 退出循环；
           - P → 切暂停（game over 时无效）；
           - R → game.restart() 并清空输入状态；
           - Esc → 退出循环。
           同时从事件构造 pressed / keydown / keyup 三个键码集合
           （pressed 来自 pygame.key.get_pressed()，keydown/keyup 来自事件）。
        5. 未暂停且未结束时：
           - action = input_controller.step(pressed, keydown, keyup)；
           - result = game.step(action, dt_ms)；
           - 若 result.events 含 GAME_OVER：用当前模式键
             mode_key(config.randomizer.mode, config.spawn_random_rotation)
             调 store.submit(key, state.score, state.level, state.lines)
             提交本局成绩（破纪录才落盘）；
             用「本局已提交」守卫标志保证一局只提交一次。
        6. renderer.draw(state, highscore, paused, game_over)；
           pygame.display.flip()。
        7. 退出循环后结束 pygame（pygame.quit()）并返回 0。
    """
    # 1. 初始化与建窗。
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("eblock - Tetris")
    clock = pygame.time.Clock()

    # 2. 装配各层。
    config = load_default_config()
    game = Game(config)
    input_controller = InputController(config.input.das_ms, config.input.arr_ms)
    renderer = Renderer(screen, config)
    store = HighscoreStore()
    key = mode_key(config.randomizer.mode, config.spawn_random_rotation)

    # 主循环状态：暂停标志、本局是否已提交高分、运行标志、当前快照。
    paused = False
    submitted = False
    running = True
    state = game.to_state()
    highscore = store.get_highscore(key)

    while running:
        # 3. 每帧：封顶 60 FPS，返回本帧经过的毫秒数。
        dt_ms = clock.tick(FPS)

        # 4. 事件处理：构造 keydown/keyup 集合，处理不进 sim 的按键。
        keydown: set[int] = set()
        keyup: set[int] = set()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p and not state.game_over:
                    paused = not paused
                elif event.key == pygame.K_r:
                    # 重开：重建对局与输入状态，重置高分提交守卫。
                    game.restart()
                    input_controller = InputController(
                        config.input.das_ms,
                        config.input.arr_ms,
                    )
                    state = game.to_state()
                    paused = False
                    submitted = False
                else:
                    keydown.add(event.key)
            elif event.type == pygame.KEYUP:
                keyup.add(event.key)

        if not running:
            break

        # 5. 未暂停且未结束时：输入 → sim → 高分提交。
        if not paused and not state.game_over:
            # pressed 来自 get_pressed()（按下集合），keydown/keyup 来自事件。
            # pygame-ce 2.5 起 get_pressed() 禁止迭代，只能按下标访问；
            # 这里只检查游戏关心的按键，再组装成 pressed 键码集合。
            key_states = pygame.key.get_pressed()
            pressed = {
                code
                for code in (
                    DEFAULT_KEYMAP.left,
                    DEFAULT_KEYMAP.right,
                    DEFAULT_KEYMAP.soft_drop,
                    DEFAULT_KEYMAP.hard_drop,
                    DEFAULT_KEYMAP.rotate_cw,
                    DEFAULT_KEYMAP.rotate_ccw,
                    DEFAULT_KEYMAP.hold,
                )
                if key_states[code]
            }
            action = input_controller.step(pressed, keydown, keyup)
            result = game.step(action, dt_ms)
            state = result.state
            if GameEvent.GAME_OVER in result.events and not submitted:
                # 用守卫标志保证一局只提交一次（破纪录才落盘）。
                store.submit(
                    key,
                    state.score,
                    state.level,
                    state.lines,
                )
                submitted = True
                highscore = store.get_highscore(key)
        else:
            # 暂停/结束后仍推进输入状态，避免按键状态残留到下一局。
            input_controller.step(set(), keydown, keyup)

        # 6. 渲染与翻页。
        renderer.draw(state, highscore, paused, state.game_over)
        pygame.display.flip()

    # 7. 收尾。
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
