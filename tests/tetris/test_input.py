"""input 模块测试（实施指南 M3）。

覆盖:
    - keydown 动作键及优先级（HOLD > ROTATE_CW > ... > SOFT_DROP_START）；
    - 左右移动的 DAS/ARR：首帧一次、满 das_ms 重复、每 arr_ms 再重复；
    - 释放清空该侧状态；左右同按清空两侧计时；
    - 软降边沿（keydown → START、keyup → END）与移动优先级。

约定：InputController.step 不接收 dt，每次调用代表一帧（=1ms），
DAS/ARR 以「按住状态下 step 的调用次数」推进计时。
"""

from eblock.tetris.sim.game import Action
from eblock.tetris.ui.input import InputController, Keymap

# 测试用独立按键映射：用普通整数键码，不依赖 pygame 常量。
KEYMAP = Keymap(
    left=0,
    right=1,
    soft_drop=2,
    hard_drop=3,
    rotate_cw=4,
    rotate_ccw=5,
    hold=6,
)


def _new_controller(das_ms: int = 170, arr_ms: int = 50) -> InputController:
    """创建带测试按键映射的输入控制器。"""
    return InputController(das_ms=das_ms, arr_ms=arr_ms, keymap=KEYMAP)


def test_keydown_hold_returns_hold_action() -> None:
    """keydown 含保持键 → 返回 HOLD。"""
    ctrl = _new_controller()
    assert ctrl.step(set(), {KEYMAP.hold}, set()) is Action.HOLD


def test_keydown_rotate_priority() -> None:
    """同一帧 HOLD 与 ROTATE_CW 同时按下 → HOLD 优先。"""
    ctrl = _new_controller()
    assert ctrl.step(set(), {KEYMAP.hold, KEYMAP.rotate_cw}, set()) is Action.HOLD


def test_hard_drop_and_soft_start_priority() -> None:
    """同一帧 HARD_DROP 与 SOFT_DROP_START 同时按下 → HARD_DROP 优先。"""
    ctrl = _new_controller()
    assert ctrl.step(set(), {KEYMAP.hard_drop, KEYMAP.soft_drop}, set()) is Action.HARD_DROP


def test_first_frame_press_moves_once() -> None:
    """首帧按下左键返回一次移动；继续按住未到 DAS 不重复。"""
    ctrl = _new_controller()
    assert ctrl.step({KEYMAP.left}, {KEYMAP.left}, set()) is Action.MOVE_LEFT
    assert ctrl.step({KEYMAP.left}, set(), set()) is None


def test_das_emits_after_delay() -> None:
    """das=170：按住第 169 帧无移动，第 170 帧触发 DAS 移动。"""
    ctrl = _new_controller(das_ms=170, arr_ms=50)
    ctrl.step({KEYMAP.left}, {KEYMAP.left}, set())  # 首帧
    for _ in range(169):
        assert ctrl.step({KEYMAP.left}, set(), set()) is None
    assert ctrl.step({KEYMAP.left}, set(), set()) is Action.MOVE_LEFT


def test_arr_repeats_every_interval() -> None:
    """das=0、arr=50：无延迟立即重复，之后每 50 帧重复一次。"""
    ctrl = _new_controller(das_ms=0, arr_ms=50)
    ctrl.step({KEYMAP.left}, {KEYMAP.left}, set())  # 首帧
    # das=0：下一帧立即进入重复阶段。
    assert ctrl.step({KEYMAP.left}, set(), set()) is Action.MOVE_LEFT
    # 之后每 50 帧一次：前 49 帧无，第 50 帧有。
    for _ in range(49):
        assert ctrl.step({KEYMAP.left}, set(), set()) is None
    assert ctrl.step({KEYMAP.left}, set(), set()) is Action.MOVE_LEFT


def test_release_resets_das() -> None:
    """释放方向键清空该侧状态：重新按下重新走首帧 + DAS 流程。"""
    ctrl = _new_controller(das_ms=170, arr_ms=50)
    ctrl.step({KEYMAP.left}, {KEYMAP.left}, set())
    for _ in range(169):
        ctrl.step({KEYMAP.left}, set(), set())
    # 释放：清空左侧状态。
    assert ctrl.step(set(), set(), {KEYMAP.left}) is None
    # 重新按下：首帧移动一次，下一帧不再立即移动。
    assert ctrl.step({KEYMAP.left}, {KEYMAP.left}, set()) is Action.MOVE_LEFT
    assert ctrl.step({KEYMAP.left}, set(), set()) is None


def test_both_directions_pressed_no_move() -> None:
    """左右同按：本帧不移动；两侧计时被清空。"""
    ctrl = _new_controller()
    # 首帧即左右同按：不返回移动。
    assert ctrl.step({KEYMAP.left, KEYMAP.right}, {KEYMAP.left, KEYMAP.right}, set()) is None
    # 按住左键推进到 DAS 前，再加入右键：仍不移动。
    ctrl.step({KEYMAP.left}, {KEYMAP.left}, set())
    for _ in range(169):
        ctrl.step({KEYMAP.left}, set(), set())
    assert ctrl.step({KEYMAP.left, KEYMAP.right}, set(), set()) is None
    # 松开右键后左键计时已清空：下一帧不会立即移动。
    assert ctrl.step({KEYMAP.left}, set(), {KEYMAP.right}) is None


def test_soft_drop_edges() -> None:
    """软降按下 → SOFT_DROP_START；松开 → SOFT_DROP_END。"""
    ctrl = _new_controller()
    assert ctrl.step(set(), {KEYMAP.soft_drop}, set()) is Action.SOFT_DROP_START
    assert ctrl.step(set(), set(), {KEYMAP.soft_drop}) is Action.SOFT_DROP_END


def test_move_beats_soft_drop_end() -> None:
    """同帧按住左（首帧移动）与松开软降 → 移动优先于 SOFT_DROP_END。"""
    ctrl = _new_controller()
    result = ctrl.step({KEYMAP.left}, {KEYMAP.left}, {KEYMAP.soft_drop})
    assert result is Action.MOVE_LEFT
