"""config：俄罗斯方块数值配置加载与校验（实施指南 M1-S1）。

职责:
    - 从 config/tetris.json 读取数值配置；
    - 加载即校验，非法配置抛 ConfigError 并指出字段路径；
    - 返回强类型冻结数据类，游戏运行时只读。

依赖方向: 本模块只依赖标准库（dataclasses / pathlib）。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


@dataclass(frozen=True)
class TetrisConfig:
    board: BoardConfig  # 棋盘配置
    scoring: ScoringConfig  # 计分配置
    gravity_ms_per_level: dict[int, int]  # 各等级重力下落间隔（毫秒/格）
    max_level: int  # 最高等级
    timing: TimingConfig  # 时序配置
    input: InputConfig  # 输入配置
    preview_count: int  # 预览方块数量


DEFAULT_CONFIG_PATH: Path = Path(__file__).resolve().parents[3] / "config" / "tetris.json"

# ==================== 第 1 层：通用原语 ====================


def _get_field(data: dict[str, Any], path: str, name: str, kind: type) -> Any:
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
    #获取值，类型判断
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
    #获取数据，类型判断
    raw = _get_field(data, path, name, dict)
    full = f"{path}.{name}" if path else name
    # 遍历 raw.items()
    result: dict[int, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.isdigit(): #键不是字符串 或 键不是数字
            raise ConfigError(full, f"键必须为数字字符串，实际为 {key!r}")
        if not isinstance(value, int) or isinstance(value, bool): #值不是数字 或 键是布尔
            raise ConfigError(f"{full}.{key}", f"类型应为 int，实际为 {type(value).__name__}")
        result[int(key)] = value
    return result

# ==================== 第 2 层：模块解析 ====================
# 一个配置块对应一个 _load_* 函数：负责「该块内部」的解析与校验。
def _load_board(data: dict[str, Any]) -> BoardConfig:
    pass
def _load_scoring(data: dict[str, Any]) -> ScoringConfig:
    pass
def _load_timing(data: dict[str, Any]) -> TimingConfig:
    pass
def _load_input(data: dict[str, Any]) -> InputConfig:
    pass
def _load_preview_count(data: dict[str, Any]) -> int:
    pass



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
    raise NotImplementedError
