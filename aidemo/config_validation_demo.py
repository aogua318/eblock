"""配置校验「分层实现」示例（以俄罗斯方块 config/tetris.json 为原型）。

演示三层结构：
    第 1 层 通用原语：_get_field / _require_range / _require_at_least / _load_int_dict
    第 2 层 模块解析：_load_board（一个配置块一个函数）
    第 3 层 入口组装：load_config_demo（读文件 + 组合 + 跨字段校验）

设计原则：
    - 单模块规则进模块解析层；跨模块规则进入口层。
    - 错误消息统一带字段路径（如「配置错误: board.cols: ...」），启动即报错、一眼定位。

本文件为教学示例：仅完整实现 board 块，其余块（scoring/timing/input）结构
完全相同，按 _load_board 的模式复制扩展即可。

直接运行：python aidemo/config_validation_demo.py
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """配置非法。消息格式：配置错误: <字段路径>: <原因>。

    进阶版：除人可读的消息外，还保留结构化的 field_path / reason 属性，
    方便调用方程序化处理（如 UI 按字段路径高亮、测试断言字段路径）。

    属性:
        field_path: 出错的字段路径（如 "board.cols"）；顶层错误为空字符串。
        reason: 失败原因描述。
    """

    def __init__(self, field_path: str, reason: str) -> None:
        self.field_path = field_path
        self.reason = reason
        # 消息格式由异常类统一保证，抛出点只需传（路径，原因）两个参数
        if field_path:
            super().__init__(f"配置错误: {field_path}: {reason}")
        else:
            super().__init__(f"配置错误: {reason}")


@dataclass(frozen=True)
class BoardConfig:
    """棋盘配置（仅示例需要，完整版见 src/eblock/tetris/config.py）。"""

    cols: int
    rows: int
    visible_rows: int
    spawn_x: int
    spawn_y: int


# ==================== 第 1 层：通用原语 ====================
# 每个函数只干一件事，全部可被多个模块复用。
# 它们是校验的「积木」：任何配置块的校验都由它们组合而成。


def _get_field(data: dict[str, Any], path: str, name: str, kind: type) -> Any:
    """取字段并校验「存在 + 类型」，失败抛 ConfigError。

    参数:
        data: 当前层级的 JSON 字典。
        path: 字段的上一级路径（如 "board"），用于拼出完整错误路径。
        name: 字段名。
        kind: 期望的 Python 类型（int/str/dict/...）。

    所有模块共用一个取字段函数，保证错误格式统一：
    缺失 → 「配置错误: board.cols: 缺少必需字段」
    类型错 → 「配置错误: board.cols: 类型应为 int，实际为 str」
    """
    full = f"{path}.{name}" if path else name
    if name not in data:
        raise ConfigError(full, "缺少必需字段")
    value = data[name]
    if not isinstance(value, kind):
        raise ConfigError(full, f"类型应为 {kind.__name__}，实际为 {type(value).__name__}")
    return value


def _require_range(value: int, path: str, lo: int, hi: int) -> None:
    """闭区间 [lo, hi] 范围校验，用于「上下界都有」的规则。"""
    if not lo <= value <= hi:
        raise ConfigError(path, f"必须在 [{lo}, {hi}] 范围内，实际为 {value}")


def _require_at_least(value: int, path: str, lo: int) -> None:
    """最小值校验，用于「只有下界」的规则（如 rows ≥ 20）。"""
    if value < lo:
        raise ConfigError(path, f"不能小于 {lo}，实际为 {value}")


def _load_int_dict(data: dict[str, Any], path: str, name: str) -> dict[int, int]:
    """把 JSON 的字符串键字典（{"1": 100}）转成 int 键字典（{1: 100}）。

    单独抽成原语的原因：line_clear 和 gravity_ms_per_level 都需要
    「键转 int + 键值类型校验」，写一次、两处复用。
    """
    raw = _get_field(data, path, name, dict)
    full = f"{path}.{name}" if path else name
    result: dict[int, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.isdigit():
            raise ConfigError(full, f"键必须为数字字符串，实际为 {key!r}")
        # 单独排除 bool：True 是 int 的子类，会混过 isinstance 检查
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigError(f"{full}.{key}", f"类型应为 int，实际为 {type(value).__name__}")
        result[int(key)] = value
    return result


# ==================== 第 2 层：模块解析 ====================
# 一个配置块对应一个 _load_* 函数：负责「该块内部」的解析与校验。
# 好处：错误消息天然带 "board." 前缀；单块规则变更只改这一个函数。


def _load_board(data: dict[str, Any]) -> BoardConfig:
    """解析 board 块，套用文档规则（每行校验对应一条设计规格）。

    步骤固定为两步：
    1. _get_field 逐个取字段（保证存在 + 类型正确）
    2. _require_* 套范围规则（保证数值合法）

    新配置块照抄此模式即可：
        def _load_scoring(data): ...   # 结构相同，字段换成 scoring 的
        def _load_timing(data): ...    # 结构相同，字段换成 timing 的
    """
    board = _get_field(data, "", "board", dict)
    config = BoardConfig(
        cols=_get_field(board, "board", "cols", int),
        rows=_get_field(board, "board", "rows", int),
        visible_rows=_get_field(board, "board", "visible_rows", int),
        spawn_x=_get_field(board, "board", "spawn_x", int),
        spawn_y=_get_field(board, "board", "spawn_y", int),
    )
    # 文档规则：cols ∈ [4, 20]；rows ≥ 20；visible_rows ∈ [1, rows]
    _require_range(config.cols, "board.cols", 4, 20)
    _require_at_least(config.rows, "board.rows", 20)
    _require_range(config.visible_rows, "board.visible_rows", 1, config.rows)
    # spawn 必须在棋盘内：x ∈ [0, cols)，y ∈ [0, rows)
    _require_range(config.spawn_x, "board.spawn_x", 0, config.cols - 1)
    _require_range(config.spawn_y, "board.spawn_y", 0, config.rows - 1)
    return config


# ==================== 第 3 层：入口组装 ====================
# load_config 只做「读文件 + 组合 + 跨字段校验」，不含任何具体字段规则。
# 跨字段规则（依赖两个以上配置块）放这里，因为只有入口能看到全貌。


def load_config_demo(path: Path) -> BoardConfig:
    """示例入口：完整走一遍加载流程，但只组装 board 块。

    真实项目 load_config 的结构完全一样，区别仅在于：
    1. 依次调用 _load_scoring / _load_timing / _load_input 等全部模块
    2. 追加跨字段校验，例如：
       - scoring.start_level ∈ [1, max_level]（依赖两块数据）
       - gravity_ms_per_level 必须连续覆盖 1..max_level（依赖两块数据）
       - 组装后返回完整的 TetrisConfig

    参数:
        path: 配置文件路径。

    返回:
        解析并校验后的 BoardConfig。

    抛出:
        ConfigError: JSON 语法错误、顶层非对象、或字段不合法。
    """
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # 语法错误路径记顶层文件名（此时还不知道任何字段路径）
        raise ConfigError(path.name, f"JSON 语法错误: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("", "顶层必须是 JSON 对象")

    return _load_board(raw)


if __name__ == "__main__":
    demo_path = Path(__file__).resolve().parents[1] / "config" / "tetris.json"
    board = load_config_demo(demo_path)
    print(f"加载成功: {board}")

    # 演示错误定位：把 cols 改成 21，观察报错信息带完整字段路径
    # bad = {"board": {"cols": 21, "rows": 22, "visible_rows": 20, "spawn_x": 4, "spawn_y": 0}}
    # 实际运行可取消注释下一行（需要 json 模块写入临时文件）
