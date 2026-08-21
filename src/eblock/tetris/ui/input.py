"""俄罗斯方块输入状态机（M3，DAS/ARR）。

把 pygame 的按键事件/按住状态翻译成 sim 层的 Action，每帧至多产出一个动作。
职责边界：本模块只做「按键 → 动作」的翻译，不含任何游戏规则；
动作的语义由 sim 层（game.py）决定。

关键设计（文档 §7.3）：
  - DAS/ARR：按住方向键首帧移动一次，之后按住满 das_ms 起每 arr_ms 再移动一次；
  - 优先级：keydown 动作键 > 左右移动 > keyup 软降结束（移动优先于 SOFT_DROP_END）；
  - 无状态泄漏：释放按键即清除该方向计时；左右同按视为无输入。
"""

from dataclasses import dataclass

import pygame

from eblock.tetris.sim.game import Action


@dataclass(frozen=True)
class Keymap:
    """按键映射：pygame 键码 → 动作。

    字段:
        left: 左移键码（默认 pygame.K_LEFT）。
        right: 右移键码（默认 pygame.K_RIGHT）。
        soft_drop: 软降键码（默认 pygame.K_DOWN，按下开始、松开结束）。
        hard_drop: 硬降键码（默认 pygame.K_SPACE）。
        rotate_cw: 顺时针旋转键码（默认 pygame.K_UP）。
        rotate_ccw: 逆时针旋转键码（默认 pygame.K_z）。
        hold: 保持键码（默认 pygame.K_c）。
    """

    left: int  # 左移键码
    right: int  # 右移键码
    soft_drop: int  # 软降键码
    hard_drop: int  # 硬降键码
    rotate_cw: int  # 顺时针旋转键码
    rotate_ccw: int  # 逆时针旋转键码
    hold: int  # 保持键码


DEFAULT_KEYMAP: Keymap = Keymap(
    left=pygame.K_LEFT,  # 左移
    right=pygame.K_RIGHT,  # 右移
    soft_drop=pygame.K_DOWN,  # 软降（按住下键）
    hard_drop=pygame.K_SPACE,  # 硬降
    rotate_cw=pygame.K_UP,  # 顺时针旋转
    rotate_ccw=pygame.K_z,  # 逆时针旋转
    hold=pygame.K_c,  # 保持
)
# 实现提示（文档 §7.2 按键映射）：
#   left=pygame.K_LEFT、right=pygame.K_RIGHT、soft_drop=pygame.K_DOWN、
#   hard_drop=pygame.K_SPACE、rotate_cw=pygame.K_UP、
#   rotate_ccw=pygame.K_z、hold=pygame.K_c。
# 实现时需要 `import pygame` 才能取这些常量。


class InputController:
    """DAS/ARR 输入状态机：把按住/按下/松开翻译成每帧至多一个 Action。

    内部字段（由 __init__ 初始化，step 只读/修改这些字段）：
        _das_ms: int 按住方向键到开始连续移动的延迟（毫秒）。
        _arr_ms: int 连续移动的重复间隔（毫秒）。
        _keymap: Keymap 按键映射。
        左右两侧各需要一组状态（以 left/right 举例，实现时自行命名）：
        _left_held: bool 该方向当前是否处于按住状态。
        _left_accum_ms: int 该方向按住累计时长（毫秒）。
        _left_first_frame: bool 该方向是否已发出过首帧移动
            （用于区分「按下瞬间」与「DAS 到期后的重复」）。
        _right_*: 与左侧对称的右移状态。
    """

    _das_ms: int
    _arr_ms: int
    _keymap: Keymap
    _left_held: bool
    _left_accum_ms: int
    _left_arr_mode: bool
    _right_held: bool
    _right_accum_ms: int
    _right_arr_mode: bool

    def __init__(
        self,
        das_ms: int,
        arr_ms: int,
        keymap: Keymap = DEFAULT_KEYMAP,
    ) -> None:
        """初始化输入状态机。

        参数:
            das_ms: 按住方向键到开始连续移动的延迟；
                0 表示无延迟，按下即进入重复阶段。
            arr_ms: 连续移动的重复间隔；0 表示每帧都移动。
            keymap: 按键映射，默认使用 DEFAULT_KEYMAP。

        返回:
            None。

        实现流程:
            1. 保存 das_ms / arr_ms / keymap 到对应字段。
            2. 初始化左右两侧状态：未按住、累计时长 0、
               尚未发出首帧移动。
        """
        # 1. 保存配置与按键映射。
        self._das_ms = das_ms
        self._arr_ms = arr_ms
        self._keymap = keymap
        # 2. 左右两侧初始状态：未按住、累计时长 0、未进入 ARR 重复阶段。
        self._left_held = False
        self._left_accum_ms = 0
        self._left_arr_mode = False
        self._right_held = False
        self._right_accum_ms = 0
        self._right_arr_mode = False

    def step(
        self,
        pressed: set[int],
        keydown: set[int],
        keyup: set[int],
    ) -> Action | None:
        """推进一帧输入，返回本帧唯一动作（无动作返回 None）。

        参数:
            pressed: 当前帧按住中的键码集合（如 pygame.key.get_pressed() 转换而来）。
            keydown: 本帧新按下的键码集合（KEYDOWN 事件）。
            keyup: 本帧新松开的键码集合（KEYUP 事件）。

        返回:
            Action 或 None。每帧至多一个动作，按下列优先级命中即返回：
            keydown 动作键 > 左右移动（DAS/ARR）> keyup 软降结束。

        实现流程（严格按文档 §5.2 行为规则）:
            1. keydown 动作键，按优先级 HOLD → ROTATE_CW → ROTATE_CCW →
               HARD_DROP → SOFT_DROP_START，命中即返回（一次只处理一个）。
            2. 左右移动（DAS/ARR）：
               - 左右**同时**在 pressed 中：本帧不返回移动，
                 并把两侧状态全部清空；
               - 仅一侧按下：
                   · 若该侧尚未发过首帧移动 → 返回一次移动并标记首帧已发；
                   · 否则累计时长：满 das_ms 起，每满 arr_ms 返回一次移动；
                   · das=0 表示无延迟立即重复，arr=0 表示每帧移动；
               - 松开（不在 pressed 中）：清空该侧状态。
            3. keyup 中的软降键 → SOFT_DROP_END
               （注意：与移动同帧时移动优先，即第 2 步先于本步判断）。
            4. 其余情况返回 None。
        """
        # 1. keydown 动作键，按优先级从上到下，命中即返回。
        if self._keymap.hold in keydown:
            return Action.HOLD
        if self._keymap.rotate_cw in keydown:
            return Action.ROTATE_CW
        if self._keymap.rotate_ccw in keydown:
            return Action.ROTATE_CCW
        if self._keymap.hard_drop in keydown:
            return Action.HARD_DROP
        if self._keymap.soft_drop in keydown:
            return Action.SOFT_DROP_START

        # 2. 左右移动（DAS/ARR）。
        left_is_held = self._keymap.left in pressed
        right_is_held = self._keymap.right in pressed
        if left_is_held and right_is_held:
            # 左右同按：本帧不返回移动，清空两侧计时与重复阶段。
            self._left_held = True
            self._left_accum_ms = 0
            self._left_arr_mode = False
            self._right_held = True
            self._right_accum_ms = 0
            self._right_arr_mode = False
            return None

        # 左侧推进。
        left_was_held = self._left_held
        self._left_accum_ms, self._left_arr_mode, action = self._advance_direction(
            left_is_held,
            left_was_held,
            self._left_accum_ms,
            self._left_arr_mode,
            Action.MOVE_LEFT,
        )
        self._left_held = left_is_held
        if action is not None:
            return action

        # 右侧推进。
        right_was_held = self._right_held
        self._right_accum_ms, self._right_arr_mode, action = self._advance_direction(
            right_is_held,
            right_was_held,
            self._right_accum_ms,
            self._right_arr_mode,
            Action.MOVE_RIGHT,
        )
        self._right_held = right_is_held
        if action is not None:
            return action

        # 3. keyup 软降结束（能走到这里说明本帧没有移动动作，移动优先）。
        if self._keymap.soft_drop in keyup:
            return Action.SOFT_DROP_END
        return None

    def _advance_direction(
        self,
        is_held: bool,
        was_held: bool,
        accum_ms: int,
        arr_mode: bool,
        move_action: Action,
    ) -> tuple[int, bool, Action | None]:
        """推进单侧 DAS/ARR 计时，返回（新累计时长, 新重复阶段, 本帧动作）。

        参数:
            is_held: 该方向按键本帧是否处于按住状态。
            was_held: 上一帧是否处于按住状态（用于识别「首帧按下」）。
            accum_ms: 该方向当前累计时长（毫秒）。
            arr_mode: 是否已过 DAS 进入 ARR 重复阶段。
            move_action: 该方向对应的移动动作（MOVE_LEFT / MOVE_RIGHT）。

        返回:
            三元组 (新累计时长, 新 arr_mode, 本帧动作或 None)。
            首帧按下立即移动一次；DAS 阶段满 das_ms 触发一次并进入 ARR；
            ARR 阶段每满 arr_ms 重复一次；松开时全部清零。
        """
        if not is_held:
            # 松开：清空计时与重复阶段。
            return 0, False, None
        if not was_held:
            # 首帧按下：立即移动一次，计时归零，尚未进入重复阶段。
            return 0, False, move_action
        if not arr_mode:
            # DAS 阶段：每帧累计 1ms，满 das_ms 触发一次移动并进入 ARR。
            accum_ms += 1
            if accum_ms >= self._das_ms:
                return 0, True, move_action
            return accum_ms, False, None
        # ARR 阶段：每满 arr_ms 重复一次移动。
        accum_ms += 1
        if accum_ms >= self._arr_ms:
            return 0, True, move_action
        return accum_ms, True, None
