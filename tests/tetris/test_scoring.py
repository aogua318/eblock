"""scoring 模块测试（实施指南 M1-S6）。

覆盖:
    - 消行计分：按 1..4 行查表，再乘以当前等级（旧等级计分）；
    - 软降 / 硬降计分：下移格数 × 每格分值；
    - 等级推进：start_level + lines // lines_per_level；
    - 重力间隔查表：超过 max_level 时按最高级速度收敛。

测试数据与 config/tetris.json 的默认值保持一致，验证数据驱动结果。
"""

import pytest

from eblock.tetris.sim.scoring import (
    gravity_interval_ms,
    hard_drop_score,
    level_after_lines,
    line_clear_score,
    soft_drop_score,
)

# 与 config/tetris.json 中 scoring.line_clear 一致：同时消 n 行的基础分。
LINE_CLEAR_TABLE = {1: 100, 2: 300, 3: 500, 4: 800}

# 与 config/tetris.json 中 gravity_ms_per_level 一致：等级 → 下落间隔（毫秒）。
GRAVITY_TABLE = {
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


def test_line_clear_score_table() -> None:
    """等级 1 时，同时消 1/2/3/4 行分别得 100/300/500/800 分。"""
    assert line_clear_score(1, level=1, table=LINE_CLEAR_TABLE) == 100
    assert line_clear_score(2, level=1, table=LINE_CLEAR_TABLE) == 300
    assert line_clear_score(3, level=1, table=LINE_CLEAR_TABLE) == 500
    assert line_clear_score(4, level=1, table=LINE_CLEAR_TABLE) == 800


def test_line_clear_multiplies_level() -> None:
    """基础分按当前等级翻倍：level=3 时消 1 行得 300 分。"""
    assert line_clear_score(1, level=3, table=LINE_CLEAR_TABLE) == 300
    assert line_clear_score(4, level=3, table=LINE_CLEAR_TABLE) == 2400


def test_soft_drop_and_hard_drop_scores() -> None:
    """软降/硬降按格数计分，每格分值分别来自各自配置项。"""
    # 软降每格 1 分：下移 3 格得 3 分。
    assert soft_drop_score(3, per_cell=1) == 3
    assert soft_drop_score(0, per_cell=1) == 0
    # 硬降每格 2 分：下移 3 格得 6 分；下移 0 格得 0 分（已在底部）。
    assert hard_drop_score(3, per_cell=2) == 6
    assert hard_drop_score(0, per_cell=2) == 0


@pytest.mark.parametrize(
    ("lines", "expected_level"),
    [
        (0, 1),  # 未消行，保持开局等级。
        (9, 1),  # 不满 10 行，不升级。
        (10, 2),  # 满 10 行，升 1 级。
        (19, 2),  # 19 行仍只升 1 级。
        (20, 3),  # 20 行升 2 级。
    ],
)
def test_level_progression(lines: int, expected_level: int) -> None:
    """每 10 行升一级，从 start_level=1 开始（整除向下取整）。"""
    assert level_after_lines(lines, lines_per_level=10, start_level=1) == expected_level


def test_gravity_interval_capped_at_max_level() -> None:
    """超过 max_level 时按 max_level 的速度下落：level 11 与 10 相同。"""
    max_level = 10
    assert gravity_interval_ms(11, GRAVITY_TABLE, max_level) == 59
    assert gravity_interval_ms(10, GRAVITY_TABLE, max_level) == 59
    # 表内各级仍按配置生效：等级 1 最慢（1000ms）。
    assert gravity_interval_ms(1, GRAVITY_TABLE, max_level) == 1000
