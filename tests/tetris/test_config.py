"""config 模块测试（实施指南 M1-S1）。

覆盖:
    - load_default_config() 读取默认配置并逐字段断言；
    - 各 _load_* 函数对非法配置的校验（缺失、类型错误、数值越界）；
    - ConfigError 消息统一带字段路径。
"""

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from eblock.tetris.config import (
    BoardConfig,
    ConfigError,
    InputConfig,
    RandomizerConfig,
    ScoringConfig,
    TetrisConfig,
    TimingConfig,
    _get_field,
    _load_board,
    _load_gravity_ms_per_level,
    _load_input,
    _load_max_level,
    _load_preview_count,
    _load_randomizer,
    _load_scoring,
    _load_spawn_random_rotation,
    _load_timing,
    load_default_config,
)

# 与 config/tetris.json 一致的默认数值，供多处复用
_GRAVITY_MS: dict[int, int] = {
    1: 1000,
    2: 793,
    3: 618,
    4: 473,
    5: 355,
    6: 262,
    7: 184,
    8: 124,
    9: 84,
    10: 59,
}


def _valid_data() -> dict[str, Any]:
    """构造一份合法的完整配置字典（与 config/tetris.json 同构）。"""
    return {
        "board": {"cols": 10, "rows": 22, "visible_rows": 20, "spawn_x": 4, "spawn_y": 0},
        "scoring": {
            "line_clear": {"1": 100, "2": 300, "3": 500, "4": 800},
            "soft_drop_per_cell": 1,
            "hard_drop_per_cell": 2,
            "lines_per_level": 10,
            "start_level": 1,
        },
        "gravity_ms_per_level": {str(k): v for k, v in _GRAVITY_MS.items()},
        "max_level": 10,
        "timing": {"lock_delay_ms": 500, "lock_reset_limit": 15, "soft_drop_interval_ms": 50},
        "input": {"das_ms": 170, "arr_ms": 50},
        "randomizer": {"mode": "seven_bag"},
        "spawn_random_rotation": False,
        "preview_count": 3,
    }


# ==================== 公共入口 ====================


def test_load_default_config_ok() -> None:
    """默认配置各字段与 config/tetris.json 及实施指南一致。"""
    config = load_default_config()
    assert isinstance(config, TetrisConfig)
    assert config.board == BoardConfig(cols=10, rows=22, visible_rows=20, spawn_x=4, spawn_y=0)
    assert config.scoring == ScoringConfig(
        line_clear={1: 100, 2: 300, 3: 500, 4: 800},
        soft_drop_per_cell=1,
        hard_drop_per_cell=2,
        lines_per_level=10,
        start_level=1,
    )
    assert config.gravity_ms_per_level == _GRAVITY_MS
    assert config.max_level == 10
    assert config.timing == TimingConfig(
        lock_delay_ms=500, lock_reset_limit=15, soft_drop_interval_ms=50
    )
    assert config.input == InputConfig(das_ms=170, arr_ms=50)
    assert config.randomizer == RandomizerConfig(mode="seven_bag")
    assert config.spawn_random_rotation is False
    assert config.preview_count == 3


def test_config_dataclasses_are_frozen() -> None:
    """冻结数据类：构造后修改字段应抛 FrozenInstanceError。"""
    board = BoardConfig(cols=10, rows=22, visible_rows=20, spawn_x=4, spawn_y=0)
    with pytest.raises(FrozenInstanceError):
        board.cols = 20


# ==================== 错误消息格式 ====================


def test_config_error_message_format() -> None:
    """错误消息统一为「配置错误: <路径>: <原因>」。"""
    with pytest.raises(ConfigError) as exc_info:
        _get_field({}, "board", "cols", int)
    assert str(exc_info.value) == "配置错误: board.cols: 缺少必需字段"
    assert exc_info.value.field_path == "board.cols"
    assert exc_info.value.reason == "缺少必需字段"


def test_field_wrong_type_reports_path() -> None:
    """类型错误消息包含字段路径与实际类型。"""
    with pytest.raises(ConfigError) as exc_info:
        _get_field({"cols": "10"}, "board", "cols", int)
    assert "board.cols" in str(exc_info.value)
    assert "实际为 str" in str(exc_info.value)


# ==================== 缺失字段 ====================


def test_missing_field_reports_path() -> None:
    """嵌套字段缺失必须报完整路径（board.cols）。"""
    data = _valid_data()
    del data["board"]["cols"]
    with pytest.raises(ConfigError, match=r"board\.cols"):
        _load_board(data)


def test_missing_section_reports_path() -> None:
    """顶层配置块缺失必须报块名（board）。"""
    data = _valid_data()
    del data["board"]
    with pytest.raises(ConfigError, match=r"^配置错误: board:"):
        _load_board(data)


# ==================== board ====================


def test_cols_out_of_range_reports_path() -> None:
    """cols=21 超上限，消息含 board.cols。"""
    data = _valid_data()
    data["board"]["cols"] = 21
    with pytest.raises(ConfigError, match=r"board\.cols"):
        _load_board(data)


def test_cols_below_min_rejected() -> None:
    """cols=3 低于下限 4。"""
    data = _valid_data()
    data["board"]["cols"] = 3
    with pytest.raises(ConfigError, match=r"board\.cols"):
        _load_board(data)


def test_rows_below_20_rejected() -> None:
    """rows=19 低于下限 20。"""
    data = _valid_data()
    data["board"]["rows"] = 19
    with pytest.raises(ConfigError, match=r"board\.rows"):
        _load_board(data)


def test_visible_rows_exceeds_rows_rejected() -> None:
    """visible_rows 不能超过 rows。"""
    data = _valid_data()
    data["board"]["visible_rows"] = 23
    with pytest.raises(ConfigError, match=r"board\.visible_rows"):
        _load_board(data)


def test_spawn_x_out_of_range_rejected() -> None:
    """spawn_x 必须 < cols。"""
    data = _valid_data()
    data["board"]["spawn_x"] = 10
    with pytest.raises(ConfigError, match=r"board\.spawn_x"):
        _load_board(data)


def test_spawn_y_out_of_range_rejected() -> None:
    """spawn_y 必须 < rows。"""
    data = _valid_data()
    data["board"]["spawn_y"] = 22
    with pytest.raises(ConfigError, match=r"board\.spawn_y"):
        _load_board(data)


def test_board_field_wrong_type_rejected() -> None:
    """board.cols 传字符串应报类型错误。"""
    data = _valid_data()
    data["board"]["cols"] = "10"
    with pytest.raises(ConfigError, match=r"board\.cols"):
        _load_board(data)


# ==================== scoring ====================


def test_line_clear_valid_keys_ok() -> None:
    """合法 line_clear（键 1..4）加载成功。"""
    config = _load_scoring(_valid_data())
    assert config.line_clear == {1: 100, 2: 300, 3: 500, 4: 800}


def test_line_clear_key_out_of_range_rejected() -> None:
    """line_clear 键超出 1..4 应拒绝。"""
    data = _valid_data()
    data["scoring"]["line_clear"] = {"1": 100, "2": 300, "3": 500, "5": 800}
    with pytest.raises(ConfigError, match=r"scoring\.line_clear"):
        _load_scoring(data)


def test_line_clear_bool_value_rejected() -> None:
    """line_clear 值为 bool 应拒绝（True 是 int 的子类）。"""
    data = _valid_data()
    data["scoring"]["line_clear"] = {"1": 100, "2": 300, "3": 500, "4": True}
    with pytest.raises(ConfigError, match=r"scoring\.line_clear"):
        _load_scoring(data)


def test_soft_drop_per_cell_zero_rejected() -> None:
    """soft_drop_per_cell=0 应拒绝（需为正整数）。"""
    data = _valid_data()
    data["scoring"]["soft_drop_per_cell"] = 0
    with pytest.raises(ConfigError, match=r"scoring\.soft_drop_per_cell"):
        _load_scoring(data)


def test_hard_drop_per_cell_zero_rejected() -> None:
    """hard_drop_per_cell=0 应拒绝（需为正整数）。"""
    data = _valid_data()
    data["scoring"]["hard_drop_per_cell"] = 0
    with pytest.raises(ConfigError, match=r"scoring\.hard_drop_per_cell"):
        _load_scoring(data)


def test_lines_per_level_zero_rejected() -> None:
    """lines_per_level=0 应拒绝（需为正整数）。"""
    data = _valid_data()
    data["scoring"]["lines_per_level"] = 0
    with pytest.raises(ConfigError, match=r"scoring\.lines_per_level"):
        _load_scoring(data)


def test_start_level_exceeds_max_level_rejected() -> None:
    """start_level 必须 ≤ max_level。"""
    data = _valid_data()
    data["scoring"]["start_level"] = 11
    with pytest.raises(ConfigError, match=r"scoring\.start_level"):
        _load_scoring(data)


# ==================== gravity_ms_per_level ====================


def test_gravity_keys_not_continuous_rejected() -> None:
    """键必须连续覆盖 1..max_level，缺 5 应拒绝。"""
    data = _valid_data()
    del data["gravity_ms_per_level"]["5"]
    with pytest.raises(ConfigError) as exc_info:
        _load_gravity_ms_per_level(data)
    assert exc_info.value.field_path == "gravity_ms_per_level"
    assert "顺序" in exc_info.value.reason


def test_gravity_keys_out_of_order_rejected() -> None:
    """键顺序必须与 1..max_level 一致。"""
    data = _valid_data()
    data["gravity_ms_per_level"] = {
        "2": 793,
        "1": 1000,
        "3": 618,
        "4": 473,
        "5": 355,
        "6": 262,
        "7": 184,
        "8": 124,
        "9": 84,
        "10": 59,
    }
    with pytest.raises(ConfigError) as exc_info:
        _load_gravity_ms_per_level(data)
    assert exc_info.value.field_path == "gravity_ms_per_level"
    assert "顺序" in exc_info.value.reason


# ==================== timing ====================


def test_lock_delay_out_of_range_rejected() -> None:
    """lock_delay_ms=99 低于下限 100。"""
    data = _valid_data()
    data["timing"]["lock_delay_ms"] = 99
    with pytest.raises(ConfigError, match=r"timing\.lock_delay_ms"):
        _load_timing(data)


def test_lock_delay_above_max_rejected() -> None:
    """lock_delay_ms=2001 高于上限 2000。"""
    data = _valid_data()
    data["timing"]["lock_delay_ms"] = 2001
    with pytest.raises(ConfigError, match=r"timing\.lock_delay_ms"):
        _load_timing(data)


def test_lock_reset_limit_negative_rejected() -> None:
    """lock_reset_limit=-1 应拒绝（需 ≥ 0）。"""
    data = _valid_data()
    data["timing"]["lock_reset_limit"] = -1
    with pytest.raises(ConfigError, match=r"timing\.lock_reset_limit"):
        _load_timing(data)


def test_soft_drop_interval_zero_rejected() -> None:
    """soft_drop_interval_ms=0 应拒绝（需 ≥ 1）。"""
    data = _valid_data()
    data["timing"]["soft_drop_interval_ms"] = 0
    with pytest.raises(ConfigError, match=r"timing\.soft_drop_interval_ms"):
        _load_timing(data)


# ==================== input ====================


def test_das_out_of_range_rejected() -> None:
    """das_ms=501 高于上限 500。"""
    data = _valid_data()
    data["input"]["das_ms"] = 501
    with pytest.raises(ConfigError, match=r"input\.das_ms"):
        _load_input(data)


def test_arr_out_of_range_rejected() -> None:
    """arr_ms=201 高于上限 200。"""
    data = _valid_data()
    data["input"]["arr_ms"] = 201
    with pytest.raises(ConfigError, match=r"input\.arr_ms"):
        _load_input(data)


# ==================== 顶层字段 ====================


def test_max_level_zero_rejected() -> None:
    """max_level=0 应拒绝（需 ≥ 1）。"""
    data = _valid_data()
    data["max_level"] = 0
    with pytest.raises(ConfigError, match=r"max_level"):
        _load_max_level(data)


def test_preview_count_zero_rejected() -> None:
    """preview_count=0 应拒绝（需 ≥ 1）。"""
    data = _valid_data()
    data["preview_count"] = 0
    with pytest.raises(ConfigError, match=r"preview_count"):
        _load_preview_count(data)


# ==================== randomizer ====================


def test_randomizer_mode_valid_ok() -> None:
    """三种合法发牌模式均可解析。"""
    for mode in ("seven_bag", "uniform", "no_repeat"):
        data = _valid_data()
        data["randomizer"]["mode"] = mode
        assert _load_randomizer(data).mode == mode


def test_randomizer_mode_invalid_rejected() -> None:
    """未知发牌模式必须报 randomizer.mode 路径。"""
    data = _valid_data()
    data["randomizer"]["mode"] = "custom_bag"
    with pytest.raises(ConfigError, match=r"randomizer\.mode"):
        _load_randomizer(data)


def test_randomizer_mode_wrong_type_rejected() -> None:
    """randomizer.mode 类型非 str 必须报类型错误。"""
    data = _valid_data()
    data["randomizer"]["mode"] = 7
    with pytest.raises(ConfigError, match=r"randomizer\.mode"):
        _load_randomizer(data)


def test_randomizer_missing_mode_reports_path() -> None:
    """randomizer.mode 缺失必须报完整路径。"""
    data = _valid_data()
    del data["randomizer"]["mode"]
    with pytest.raises(ConfigError, match=r"randomizer\.mode"):
        _load_randomizer(data)


def test_randomizer_section_missing_reports_path() -> None:
    """顶层 randomizer 块缺失必须报 randomizer。"""
    data = _valid_data()
    del data["randomizer"]
    with pytest.raises(ConfigError, match=r"randomizer"):
        _load_randomizer(data)


# ==================== spawn_random_rotation ====================


def test_spawn_random_rotation_true_ok() -> None:
    """spawn_random_rotation=true 合法。"""
    data = _valid_data()
    data["spawn_random_rotation"] = True
    assert _load_spawn_random_rotation(data) is True


def test_spawn_random_rotation_int_rejected() -> None:
    """spawn_random_rotation=1 不是合法布尔，必须报类型错误。"""
    data = _valid_data()
    data["spawn_random_rotation"] = 1
    with pytest.raises(ConfigError, match=r"spawn_random_rotation"):
        _load_spawn_random_rotation(data)


def test_spawn_random_rotation_str_rejected() -> None:
    """spawn_random_rotation="true" 不是合法布尔，必须报类型错误。"""
    data = _valid_data()
    data["spawn_random_rotation"] = "true"
    with pytest.raises(ConfigError, match=r"spawn_random_rotation"):
        _load_spawn_random_rotation(data)


def test_spawn_random_rotation_missing_reports_path() -> None:
    """spawn_random_rotation 缺失必须报完整路径。"""
    data = _valid_data()
    del data["spawn_random_rotation"]
    with pytest.raises(ConfigError, match=r"spawn_random_rotation"):
        _load_spawn_random_rotation(data)
