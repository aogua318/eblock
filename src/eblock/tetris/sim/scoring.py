"""俄罗斯方块计分、等级推进与重力间隔查表（纯函数）。

本模块集中处理三类"查表/算术"逻辑：
  1. 消行、软降、硬降三种场景的计分；
  2. 根据累计消除行数计算当前等级；
  3. 根据等级查询自动下落间隔。
全部是纯函数：不修改外部状态、不读取全局变量，结果只由参数决定，
因此可以脱离 pygame 独立运行，也便于用单元测试逐条覆盖。
所有数值来源（分数表、每行升级数、各级重力间隔）都由调用方从
config/tetris.json 传入，本模块内不硬编码任何游戏数值。
"""

from collections.abc import Mapping


def line_clear_score(lines_cleared: int, level: int, table: Mapping[int, int]) -> int:
    """计算一次消行获得的基础分。

    参数:
        lines_cleared: 本次同时消除的行数。调用方（game.py 锁定流程）保证
            只传入 1..4，本函数不负责校验范围，只做查表与乘法。
        level: 消行发生时的当前等级。注意锁定流程要求按"旧等级"计分，
            即先算分、后升级，因此这里传入的是升级前的等级。
        table: 消行分数表，键为同时消行数，值为该档基础分
            （来自 config/scoring.line_clear，如 1→100、4→800）。

    返回:
        本次消行得分，等于 table[lines_cleared] * level。

    实现流程:
        1. 用 lines_cleared 在 table 中查到该档基础分；
        2. 将基础分乘以当前等级，作为返回值。
    """
    # 实现提示：
    # 1. 用 lines_cleared 查 table，得到该档基础分。
    # 2. 基础分 * level 即为返回值。
    # 注意：不要在函数里校验 lines_cleared 的范围或做"缺键兜底"，
    #       保持最小职责——非法输入由调用方负责。
    # score_base = table[lines_cleared]

    return level * table[lines_cleared]


def soft_drop_score(cells: int, per_cell: int) -> int:
    """计算软降（按住下键逐格下落）的累计得分。

    参数:
        cells: 软降实际下移的总格数（game.py 每成功下移一格就累加一次）。
        per_cell: 每下移一格的基础分（来自 config/scoring.soft_drop_per_cell）。

    返回:
        软降得分，等于 cells * per_cell。

    实现流程:
        1. 每下移一格固定加 per_cell 分；
        2. 总得分 = 下移格数 × 每格分数。
    """
    # 实现提示：
    # 1. 这是最简单的乘法，直接返回 cells * per_cell。
    # 2. 无需保存任何状态：本函数只负责"换算"，累加逻辑在 game.py 里。
    return cells * per_cell


def hard_drop_score(cells: int, per_cell: int) -> int:
    """计算硬降（瞬间落到最底）的得分。

    参数:
        cells: 硬降实际下移的总格数（从当前位置到落点的距离，
            可由 game.py 的 ghost_y 相关逻辑算出）。
        per_cell: 每下移一格的基础分（来自 config/scoring.hard_drop_per_cell）。

    返回:
        硬降得分，等于 cells * per_cell。

    实现流程:
        1. 硬降按"下移了多少格"计分，与软降算法相同，只是每格分值不同；
        2. 总得分 = 下移格数 × 每格分数。
    """
    # 实现提示：
    # 1. 与 soft_drop_score 结构相同，直接返回 cells * per_cell。
    # 2. 距离为 0 时结果应为 0，属于合法情况（方块已在底部硬降）。
    return cells * per_cell


def level_after_lines(
    lines: int,
    lines_per_level: int,
    start_level: int,
) -> int:
    """根据累计消除行数计算应处的等级。

    参数:
        lines: 本局累计消除的总行数（game.py 的 _lines 字段）。
        lines_per_level: 每消除多少行升一级（来自 config/scoring.lines_per_level）。
        start_level: 开局等级（来自 config/scoring.start_level，通常为 1）。

    返回:
        新等级，等于 start_level + lines // lines_per_level（整除向下取整）。

    实现流程:
        1. 用整除（//）算出从开局到现在一共升了几级；
        2. 在 start_level 基础上加上升级次数，即为新等级。
    """
    # 实现提示：
    # 1. lines // lines_per_level：整除，余数部分不构成升级。
    # 2. 返回值 = start_level + 升级次数。
    # 边界例子（start_level=1、lines_per_level=10）：
    #   lines=9  → 0 次升级 → 等级不变（1）；
    #   lines=10 → 1 次升级 → 等级 2；
    #   lines=19 → 1 次升级 → 等级 2；lines=20 → 等级 3。
    return lines // lines_per_level + start_level


def gravity_interval_ms(
    level: int,
    table: Mapping[int, int],
    max_level: int,
) -> int:
    """查询某等级对应的自动下落间隔（毫秒）。

    参数:
        level: 当前等级，可能超过 max_level（配置允许等级无限增长）。
        table: 等级→下落间隔查表（来自 config/gravity_ms_per_level，
            键连续覆盖 1..max_level，值为正毫秒数，越小下落越快）。
        max_level: 查表支持的最高等级（来自 config/max_level）。

    返回:
        该等级的下落间隔毫秒数。level 超过 max_level 时按 max_level 的速度
        下落（即取 table[min(level, max_level)]）。

    实现流程:
        1. 先取有效等级 = min(level, max_level)，把越界等级收敛到表内；
        2. 用有效等级在 table 中查到对应毫秒数并返回。
    """
    # 实现提示：
    # 1. 等级高于 max_level 时不能直接查表（键不存在）
    # 2. 表内键已由 config 校验为连续覆盖 1..max_level，因此收敛后
    #    查表不会缺键，无需再写兜底分支。
    if level >= max_level:
        return table[max_level]

    return table[level]
