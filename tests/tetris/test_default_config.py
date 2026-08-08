"""load_default_config() 公共入口端到端测试。

只通过公共入口 load_default_config() 读取 config/tetris.json，
不触碰任何 _load_* 内部函数。覆盖:
    - 返回值为冻结的 TetrisConfig，各字段与磁盘配置文件一致；
    - 默认配置满足实施指南的全部约束（范围、连续性、正值）；
    - 重复调用结果稳定（幂等）。
"""

import json
from dataclasses import FrozenInstanceError

import pytest

from eblock.tetris.config import (
    DEFAULT_CONFIG_PATH,
    TetrisConfig,
    load_default_config,
)

# ==================== 文件与入口 ====================


def test_config_file_exists() -> None:
    """默认配置文件必须存在且可读。"""
    assert DEFAULT_CONFIG_PATH.is_file()


def test_load_default_config_returns_config() -> None:
    """直接调用 load_default_config() 返回 TetrisConfig 实例。"""
    config = load_default_config()
    assert isinstance(config, TetrisConfig)

