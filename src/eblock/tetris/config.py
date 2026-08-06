from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """配置非法。消息格式：配置错误: <字段路径>: <原因>。

    属性:
        field_path: 出错的字段路径（如 "board.cols"）；顶层错误为空字符串。
        reason: 失败原因描述。
    """

    def __init__(self, field_path: str, reason: str) -> None:
        self.field_path = field_path
        self.reason = reason
        if field_path:
            super().__init__(f"配置错误: {field_path}: {reason}")
        else:
            super().__init__(f"配置错误: {reason}")


@dataclass(frozen=True)
class BoardConfig:
    cols: int          # 列数（棋盘宽度）
    rows: int          # 总行数（含隐藏区）
    visible_rows: int  # 可见行数（屏幕显示区域）
    spawn_x: int       # 出生点列坐标
    spawn_y: int       # 出生点行坐标


@dataclass(frozen=True)
class ScoringConfig:
    line_clear: dict[int, int]  # 一次消 n 行所得分数
    soft_drop_per_cell: int     # 软降每格得分
    hard_drop_per_cell: int     # 硬降每格得分
    lines_per_level: int        # 每升一级所需消行数
    start_level: int            # 起始等级


@dataclass(frozen=True)
class TimingConfig:
    lock_delay_ms: int          # 落地后允许移动/旋转的锁定延迟
    lock_reset_limit: int       # 锁定延迟可重置次数上限
    soft_drop_interval_ms: int  # 软降时每格下落间隔（毫秒）


@dataclass(frozen=True)
class InputConfig:
    das_ms: int  # 按住方向键到开始自动移动的延迟（毫秒）
    arr_ms: int  # 自动移动的间隔（毫秒）


@dataclass(frozen=True)
class TetrisConfig:
    board: BoardConfig                     # 棋盘配置
    scoring: ScoringConfig                 # 计分配置
    gravity_ms_per_level: dict[int, int]   # 各等级重力下落间隔（毫秒/格）
    max_level: int                         # 最高等级
    timing: TimingConfig                   # 时序配置
    input: InputConfig                     # 输入配置
    preview_count: int                     # 预览方块数量


DEFAULT_CONFIG_PATH: Path = Path(__file__).resolve().parents[3] / "config" / "tetris.json"


def load_config(path: Path) -> TetrisConfig: ...
def load_default_config() -> TetrisConfig: ...
