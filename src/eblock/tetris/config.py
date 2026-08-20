"""config：俄罗斯方块数值配置加载与校验（实施指南 M1-S1）。

职责:
    - 从 config/tetris.json 读取数值配置；
    - 加载即校验，非法配置抛 ConfigError 并指出字段路径；
    - 返回强类型冻结数据类，游戏运行时只读。

依赖方向: 本模块只依赖标准库（dataclasses / pathlib）。
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast


class ConfigError(ValueError):
    """配置非法时抛出的异常。

    消息格式: 配置错误: <字段路径>: <原因>；顶层错误（如 JSON 语法错误）
    无字段路径前缀。

    属性:
        field_path: 出错的字段路径（如 "board.cols"）；顶层错误为空字符串。
        reason: 失败原因描述。

    抛出场景:
        - JSON 语法错误;
        - 字段缺失或类型错误;
        - 数值超出校验范围。

    实现提示:
        - 构造器 __init__(self, field_path: str, reason: str) -> None:
          保存 self.field_path / self.reason 两个属性，再按上面的消息格式
          拼接字符串并调用 super().__init__；
        - 抛出点统一传 (路径, 原因) 两个参数，由本类保证消息格式一致。
    """

    def __init__(self, field_path: str, reason: str) -> None:
        """记录字段路径与原因，并按统一格式生成消息。"""
        self.field_path = field_path
        self.reason = reason
        super().__init__(f"配置错误: {field_path}: {reason}")


@dataclass(frozen=True)
class BoardConfig:
    cols: int  # 列数（棋盘宽度）
    rows: int  # 总行数（含隐藏区）
    visible_rows: int  # 可见行数（屏幕显示区域）
    spawn_x: int  # 出生点列坐标
    spawn_y: int  # 出生点行坐标


@dataclass(frozen=True)
class ScoringConfig:
    line_clear: dict[int, int]  # 一次消 n 行所得分数
    soft_drop_per_cell: int  # 软降每格得分
    hard_drop_per_cell: int  # 硬降每格得分
    lines_per_level: int  # 每升一级所需消行数
    start_level: int  # 起始等级


@dataclass(frozen=True)
class TimingConfig:
    lock_delay_ms: int  # 落地后允许移动/旋转的锁定延迟
    lock_reset_limit: int  # 锁定延迟可重置次数上限
    soft_drop_interval_ms: int  # 软降时每格下落间隔（毫秒）


@dataclass(frozen=True)
class InputConfig:
    das_ms: int  # 按住方向键到开始自动移动的延迟（毫秒）
    arr_ms: int  # 自动移动的间隔（毫秒）


# 发牌算法模式：seven_bag=7-bag 全排列；uniform=每次独立等概率；
# no_repeat=保证连续两次不出同一方块。
# Literal 必须是[]里的值
RandomizerMode = Literal["seven_bag", "uniform", "no_repeat"]

# 合法发牌模式集合，供校验与错误消息复用。
_RANDOMIZER_MODES: frozenset[str] = frozenset({"seven_bag", "uniform", "no_repeat"})


@dataclass(frozen=True)
class RandomizerConfig:
    mode: RandomizerMode  # 发牌算法模式（见 RandomizerMode 说明）


@dataclass(frozen=True)
class TetrisConfig:
    board: BoardConfig  # 棋盘配置
    scoring: ScoringConfig  # 计分配置
    gravity_ms_per_level: dict[int, int]  # 各等级重力下落间隔（毫秒/格）
    max_level: int  # 最高等级
    timing: TimingConfig  # 时序配置
    input: InputConfig  # 输入配置
    randomizer: RandomizerConfig  # 发牌器配置（决定方块随机算法）
    spawn_random_rotation: bool  # 出生时是否随机旋转（true=随机 0..3 方向）
    preview_count: int  # 预览方块数量


DEFAULT_CONFIG_PATH: Path = Path(__file__).resolve().parents[3] / "config" / "tetris.json"

# ==================== 第 1 层：通用原语 ====================


def _get_field[T](data: dict[str, Any], path: str, name: str, kind: type[T]) -> T:
    """取字段并校验「存在 + 类型」，失败抛 ConfigError（通用原语 1）。

    所有模块共用一个取字段函数，保证错误格式统一：
        缺失 → 「配置错误: board.cols: 缺少必需字段」
        类型错 → 「配置错误: board.cols: 类型应为 int，实际为 str」

    参数:
        data: 当前层级的 JSON 字典。
        path: 字段的上一级路径（如 "board"）；顶层字段传 ""。
        name: 字段名（如 "cols"）。
        kind: 期望的 Python 类型（int / str / dict / ...）。

    返回:
        校验通过后的字段值（类型由 kind 保证）。

    抛出:
        ConfigError: 字段缺失，或类型与 kind 不符。
    """
    # 如果path不存在,full = name
    full = f"{path}.{name}" if path else name
    if name not in data:
        raise ConfigError(full, "缺少必需字段")
    # 获取值，类型判断
    value = data[name]
    if not isinstance(value, kind):
        raise ConfigError(full, f"类型应为 {kind.__name__}，实际为 {type(value).__name__}")
    return value


def _require_range(value: int, path: str, lo: int, hi: int) -> None:
    """闭区间 [lo, hi] 范围校验（通用原语 2），用于「上下界都有」的规则。

    参数:
        value: 已通过类型校验的 int。
        path: 完整错误路径（如 "board.cols"）。
        lo: 下界，含。
        hi: 上界，含。

    返回:
        None（校验不通过直接抛异常）。

    抛出:
        ConfigError: value 不在 [lo, hi] 内，消息含范围与实际值。
    """
    if not lo <= value <= hi:
        raise ConfigError(path, f"必须在 [{lo}, {hi}] 范围内，实际为 {value}")


def _require_at_least(value: int, path: str, lo: int) -> None:
    """最小值校验（通用原语 3），用于「只有下界」的规则（如 rows ≥ 20）。

    参数:
        value: 已通过类型校验的 int。
        path: 完整错误路径（如 "board.rows"）。
        lo: 下界，含。

    返回:
        None（校验不通过直接抛异常）。

    抛出:
        ConfigError: value < lo，消息含下界与实际值。
    """
    if value < lo:
        raise ConfigError(path, f"不能小于 {lo}，实际为 {value}")


def _load_int_dict(data: dict[str, Any], path: str, name: str) -> dict[int, int]:
    """把 JSON 字符串键字典（{"1": 100}）转成 int 键字典（{1: 100}）（通用原语 4）。

    line_clear 与 gravity_ms_per_level 都需要「键转 int + 键值类型校验」，
    单独抽成原语，写一次、两处复用。

    参数:
        data: 当前层级的 JSON 字典。
        path: 字段的上一级路径（如 "scoring"）；顶层字段传 ""。
        name: 字段名（如 "line_clear"）。

    返回:
        键与值均为 int 的新字典。

    抛出:
        ConfigError: 字段缺失或不是 dict（由 _get_field 抛出）；
                     键不是数字字符串；
                     值不是 int（需单独排除 bool：True 是 int 的子类）。
    """
    # 获取数据，类型判断
    raw = _get_field(data, path, name, dict)
    full = f"{path}.{name}" if path else name
    # 遍历 raw.items()
    result: dict[int, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.isdigit():  # 键不是字符串 或 键不是数字
            raise ConfigError(full, f"键必须为数字字符串，实际为 {key!r}")
        if not isinstance(value, int) or isinstance(value, bool):  # 值不是数字 或 键是布尔
            raise ConfigError(f"{full}.{key}", f"类型应为 int，实际为 {type(value).__name__}")
        result[int(key)] = value
    return result


# ==================== 第 2 层：模块解析 ====================
# 一个配置块对应一个 _load_* 函数：负责「该块内部」的解析与校验。
def _load_board(data: dict[str, Any]) -> BoardConfig:
    """
    `board.cols` 4–20 的整数；
    `board.rows` ≥ 20；
    `board.visible_rows` 1 ≤ v ≤ rows；
    `board.spawn_x` ∈ [0, cols)；
    `board.spawn_y` ∈ [0, rows)。
    """
    # 类型判断
    board = _get_field(data, "", "board", dict)
    config = BoardConfig(
        cols=_get_field(board, "board", "cols", int),
        rows=_get_field(board, "board", "rows", int),
        visible_rows=_get_field(board, "board", "visible_rows", int),
        spawn_x=_get_field(board, "board", "spawn_x", int),
        spawn_y=_get_field(board, "board", "spawn_y", int),
    )
    # 规则判断
    _require_range(config.cols, "board.cols", 4, 20)
    _require_at_least(config.rows, "board.rows", 20)
    _require_range(config.visible_rows, "board.visible_rows", 1, config.rows)
    _require_range(config.spawn_x, "board.spawn_x", 0, config.cols - 1)
    _require_range(config.spawn_y, "board.spawn_y", 0, config.rows - 1)
    return config


def _load_scoring(data: dict[str, Any]) -> ScoringConfig:
    """
    - `scoring.line_clear` 的键必须恰好是 1、2、3、4（JSON 中是字符串，先转 int），值均为正整数；
    - `soft_drop_per_cell`、`hard_drop_per_cell`、`lines_per_level` 为正整数；
    - `start_level` ∈ [1, max_level]。
    """
    scoring = _get_field(data, "", "scoring", dict)
    config = ScoringConfig(
        line_clear=_load_int_dict(scoring, "scoring", "line_clear"),
        soft_drop_per_cell=_get_field(scoring, "scoring", "soft_drop_per_cell", int),
        hard_drop_per_cell=_get_field(scoring, "scoring", "hard_drop_per_cell", int),
        lines_per_level=_get_field(scoring, "scoring", "lines_per_level", int),
        start_level=_get_field(scoring, "scoring", "start_level", int),
    )

    for key in config.line_clear:
        _require_range(key, "scoring.line_clear", 1, 4)

    _require_at_least(config.soft_drop_per_cell, "scoring.soft_drop_per_cell", 1)
    _require_at_least(config.hard_drop_per_cell, "scoring.hard_drop_per_cell", 1)
    _require_at_least(config.lines_per_level, "scoring.lines_per_level", 1)

    max_level = _get_field(data, "", "max_level", int)
    _require_range(config.start_level, "scoring.start_level", 1, max_level)

    return config


def _load_gravity_ms_per_level(data: dict[str, Any]) -> dict[int, int]:
    """
    - `gravity_ms_per_level` 的键转 int 后必须连续覆盖 1..max_level，值均为正数。
    """
    config = _load_int_dict(data, "", "gravity_ms_per_level")
    max_level = _get_field(data, "", "max_level", int)
    key_list = []
    for key in config:
        key_list.append(key)
    expected_keys = list(range(1, max_level + 1))

    if not key_list == expected_keys:
        raise ConfigError(
            "gravity_ms_per_level", f"key 顺序错误:实际顺序为 {key_list}，预期为 {expected_keys}。"
        )

    return config


def _load_timing(data: dict[str, Any]) -> TimingConfig:
    """
    - `timing.lock_delay_ms` ∈ [100, 2000]；
    - `lock_reset_limit` ≥ 0；
    - `soft_drop_interval_ms` ≥ 1。
    """
    timing = _get_field(data, "", "timing", dict)
    config = TimingConfig(
        lock_delay_ms=_get_field(timing, "timing", "lock_delay_ms", int),
        lock_reset_limit=_get_field(timing, "timing", "lock_reset_limit", int),
        soft_drop_interval_ms=_get_field(timing, "timing", "soft_drop_interval_ms", int),
    )
    _require_range(config.lock_delay_ms, "timing.lock_delay_ms", 100, 2000)
    _require_at_least(config.lock_reset_limit, "timing.lock_reset_limit", 0)
    _require_at_least(config.soft_drop_interval_ms, "timing.soft_drop_interval_ms", 1)
    return config


def _load_input(data: dict[str, Any]) -> InputConfig:
    """
    - `input.das_ms` ∈ [0, 500]；
    - `input.arr_ms` ∈ [0, 200]。
    """
    input_time = _get_field(data, "", "input", dict)
    config = InputConfig(
        das_ms=_get_field(input_time, "input", "das_ms", int),
        arr_ms=_get_field(input_time, "input", "arr_ms", int),
    )
    _require_range(config.das_ms, "input.das_ms", 0, 500)
    _require_range(config.arr_ms, "input.arr_ms", 0, 200)
    return config


def _load_randomizer(data: dict[str, Any]) -> RandomizerConfig:
    """解析并校验发牌器配置（randomizer.mode）。

    `randomizer.mode` 必须是 seven_bag / uniform / no_repeat 三者之一；
    其他取值视为非法配置，错误消息带完整字段路径。

    参数:
        data: 顶层配置字典。

    返回:
        校验通过后的 RandomizerConfig。

    抛出:
        ConfigError: randomizer 块缺失、mode 缺失、类型非 str，
            或取值不在合法模式集合内。
    """
    randomizer = _get_field(data, "", "randomizer", dict)
    mode_raw = _get_field(randomizer, "randomizer", "mode", str)
    if mode_raw not in _RANDOMIZER_MODES:
        modes = ", ".join(sorted(_RANDOMIZER_MODES))
        raise ConfigError("randomizer.mode", f"必须是 {modes} 之一，实际为 {mode_raw!r}")
    return RandomizerConfig(mode=cast(RandomizerMode, mode_raw))


def _load_spawn_random_rotation(data: dict[str, Any]) -> bool:
    """解析并校验出生随机旋转开关（spawn_random_rotation）。

    该字段必须是 JSON 布尔值 true/false；数字 0/1 不是合法布尔，
    会被类型校验拒绝（isinstance(0, bool) 为 False）。

    参数:
        data: 顶层配置字典。

    返回:
        校验通过后的布尔值；True 表示新方块出生时随机取 0..3 旋转状态。

    抛出:
        ConfigError: 字段缺失或类型不是 bool。
    """
    return _get_field(data, "", "spawn_random_rotation", bool)


def _load_max_level(data: dict[str, Any]) -> int:
    """- `max_level` ≥ 1。"""
    max_level = _get_field(data, "", "max_level", int)
    _require_at_least(max_level, "max_level", 1)
    return max_level


def _load_preview_count(data: dict[str, Any]) -> int:
    """- `preview_count` ≥ 1。"""
    preview_count = _get_field(data, "", "preview_count", int)
    _require_at_least(preview_count, "preview_count", 1)
    return preview_count


def load_default_config() -> TetrisConfig:
    """加载项目默认配置（DEFAULT_CONFIG_PATH）。

    输入:
        无。

    返回:
        校验通过的 TetrisConfig。

    抛出:
        ConfigError: 默认配置非法（见 load_config）。
        FileNotFoundError: 默认配置文件缺失。
    """
    with open(DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # 解析配置 并返回
    return TetrisConfig(
        board=_load_board(data),  # 棋盘配置
        scoring=_load_scoring(data),  # 计分配置
        gravity_ms_per_level=_load_gravity_ms_per_level(data),  # 各等级重力下落间隔（毫秒/格）
        max_level=_load_max_level(data),  # 最高等级
        timing=_load_timing(data),  # 时序配置
        input=_load_input(data),  # 输入配置
        randomizer=_load_randomizer(data),  # 发牌器配置
        spawn_random_rotation=_load_spawn_random_rotation(data),  # 出生随机旋转开关
        preview_count=_load_preview_count(data),  # 预览方块数量
    )
