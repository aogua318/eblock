"""按模式分组的高分持久化（M2 高分存档，模式独立）。

模式键由玩法设置组合而成（发牌模式 + 出生旋转开关），例如：
    seven_bag_fixed / uniform_random / no_repeat_random
同一模式键下只保留最高一条纪录，不同模式互不影响。

文件格式（saves/highscores.json）：
    {
      "seven_bag_fixed": { "score": 100, "level": 1, "lines": 0, "date": "2026-08-15" },
      "uniform_random":  { "score": 80,  "level": 1, "lines": 0, "date": "2026-08-15" }
    }

读取时逐模式校验；单条纪录非法则跳过并警告，整个文件损坏则回退为空记录，
保证运行期不因存档损坏而崩溃。本模块只依赖标准库。
"""

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

# 默认高分文件路径：<仓库根>/saves/highscores.json。
DEFAULT_HIGHSCORE_PATH: Path = Path(__file__).resolve().parents[4] / "saves" / "highscores.json"


@dataclass(frozen=True)
class HighScore:
    """单条最高分纪录（不可变数据类）。

    字段:
        score: 最高分（非负整数）。
        level: 达成该分数时的等级。
        lines: 达成该分数时的累计消行数。
        date: 达成日期，ISO 格式字符串（如 2026-08-15）。
    """

    score: int
    level: int
    lines: int
    date: str


def new_highscore(score: int, level: int, lines: int) -> HighScore:
    """构造一条新的最高分纪录，日期取今天。

    参数:
        score: 分数（非负整数）。
        level: 等级（非负整数）。
        lines: 累计消行数（非负整数）。

    返回:
        date 为 datetime.date.today().isoformat() 的 HighScore。
    """
    return HighScore(score=score, level=level, lines=lines, date=date.today().isoformat())


def mode_key(randomizer_mode: str, spawn_random_rotation: bool) -> str:
    """按玩法设置生成独立计分模式键。

    参数:
        randomizer_mode: 发牌算法模式（seven_bag / uniform / no_repeat）。
        spawn_random_rotation: 出生是否随机旋转。

    返回:
        模式键，格式为 <发牌模式>_<fixed|random>，例如 seven_bag_fixed。
    """
    rotation_part = "random" if spawn_random_rotation else "fixed"
    return f"{randomizer_mode}_{rotation_part}"


def is_new_record(score: int, current: HighScore) -> bool:
    """判断 score 是否严格高于当前纪录。

    参数:
        score: 待判断的分数。
        current: 当前最高分纪录。

    返回:
        True 表示破纪录；等于当前纪录不算破纪录（严格大于）。
    """
    return score > current.score


def _warn(message: str) -> None:
    """向 stderr 输出警告（存档损坏时提示，不中断运行）。"""
    print(f"警告: {message}", file=sys.stderr)


def _parse_record(raw: Any) -> HighScore | None:
    """把单个模式的 JSON 值解析为 HighScore。

    参数:
        raw: 从 JSON 读取的任意值（应为 dict）。

    返回:
        校验通过后的 HighScore；结构或类型非法时返回 None。
    """
    if not isinstance(raw, dict):
        return None
    score = raw.get("score")
    level = raw.get("level")
    lines = raw.get("lines")
    date_value = raw.get("date")
    if not isinstance(score, int) or isinstance(score, bool) or score < 0:
        return None
    if not isinstance(level, int) or isinstance(level, bool) or level < 0:
        return None
    if not isinstance(lines, int) or isinstance(lines, bool) or lines < 0:
        return None
    if not isinstance(date_value, str) or not date_value:
        return None
    return HighScore(score=score, level=level, lines=lines, date=date_value)


def load_highscores(path: Path) -> dict[str, HighScore]:
    """读取整个高分文件，返回「模式键 → 最高分纪录」映射。

    参数:
        path: 高分文件路径。

    返回:
        模式键到 HighScore 的字典；文件缺失、JSON 损坏或整体不是对象时
        返回空字典并警告；单条纪录非法时跳过该条并警告。
    """
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _warn(f"高分文件读取失败（{path}），已回退为空纪录: {exc}")
        return {}
    if not isinstance(raw, dict):
        _warn(f"高分文件内容不是对象（{path}），已回退为空纪录")
        return {}
    records: dict[str, HighScore] = {}
    for key, value in raw.items():
        record = _parse_record(value)
        if record is None:
            _warn(f"模式 {key!r} 的高分纪录非法，已跳过")
            continue
        records[key] = record
    return records


def save_highscores(path: Path, records: Mapping[str, HighScore]) -> None:
    """把全部模式纪录写入 JSON 文件。

    参数:
        path: 目标文件路径。
        records: 模式键到 HighScore 的映射。

    返回:
        None（父目录不存在时自动创建）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        key: {
            "score": record.score,
            "level": record.level,
            "lines": record.lines,
            "date": record.date,
        }
        for key, record in records.items()
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class HighscoreStore:
    """按模式分组的高分存储（内存缓存 + JSON 持久化）。

    用法：
        store = HighscoreStore()
        if store.submit(mode_key("seven_bag", False), 100, 1, 0):
            print("新纪录")

    构造时自动从磁盘加载；文件损坏时回退为空记录并警告，不崩溃。
    """

    def __init__(self, path: Path = DEFAULT_HIGHSCORE_PATH) -> None:
        """初始化存储并加载磁盘上的既有纪录。

        参数:
            path: 高分文件路径，默认 saves/highscores.json。
        """
        self._path = path
        self._records: dict[str, HighScore] = {}
        self.reload()

    def reload(self) -> None:
        """从磁盘重新加载全部模式纪录（覆盖内存缓存）。"""
        self._records = load_highscores(self._path)

    def get_highscore(self, key: str) -> HighScore:
        """返回指定模式键的最高分纪录。

        参数:
            key: 模式键（见 mode_key）。

        返回:
            该模式的 HighScore；无纪录时返回全零默认 HighScore(0, 0, 0, "")。
        """
        return self._records.get(key, HighScore(score=0, level=0, lines=0, date=""))

    def submit(self, key: str, score: int, level: int, lines: int) -> bool:
        """提交一局成绩：破纪录则更新内存并落盘。

        参数:
            key: 模式键（见 mode_key），不同模式纪录互不影响。
            score: 本局分数。
            level: 本局结束时的等级。
            lines: 本局累计消行数。

        返回:
            True 表示本局打破该模式纪录；False 表示未破纪录（未写盘）。
        """
        current = self.get_highscore(key)
        if not is_new_record(score, current):
            return False
        self._records[key] = new_highscore(score, level, lines)
        self.save()
        return True

    def save(self) -> None:
        """把内存中的全部模式纪录写入 JSON 文件。"""
        save_highscores(self._path, self._records)
