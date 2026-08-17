"""highscore 模块测试（M2 高分存档：模式独立）。

覆盖:
    - 文件缺失 / JSON 损坏 / 字段类型非法 → 回退默认值并警告；
    - 保存与读取往返一致；父目录不存在时自动创建；
    - new_highscore 日期取今天；is_new_record 严格大于；
    - mode_key 由发牌模式与出生旋转组合；
    - HighscoreStore 按模式键独立计录，互不影响。
"""

import json
from datetime import date
from pathlib import Path

import pytest

from eblock.tetris.save.highscore import (
    DEFAULT_HIGHSCORE_PATH,
    HighScore,
    HighscoreStore,
    is_new_record,
    load_highscores,
    mode_key,
    new_highscore,
    save_highscores,
)


def _valid_record(score: int = 100) -> dict[str, int | str]:
    """构造一条合法的高分 JSON 记录。"""
    return {"score": score, "level": 1, "lines": 0, "date": "2026-08-15"}


# ==================== 文件读写 ====================


def test_default_path_points_to_saves_dir() -> None:
    """默认高分路径位于仓库根下的 saves 目录。"""
    assert DEFAULT_HIGHSCORE_PATH.name == "highscores.json"
    assert DEFAULT_HIGHSCORE_PATH.parent.name == "saves"


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    """文件不存在时返回空字典，不抛异常。"""
    assert load_highscores(tmp_path / "missing.json") == {}


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    """保存后读取，模式键与纪录内容一致。"""
    path = tmp_path / "scores.json"
    record = HighScore(score=120, level=2, lines=3, date="2026-08-15")
    save_highscores(path, {"seven_bag_fixed": record})
    loaded = load_highscores(path)
    assert loaded == {"seven_bag_fixed": record}


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """父目录不存在时 save_highscores 自动创建。"""
    path = tmp_path / "nested" / "deep" / "scores.json"
    save_highscores(path, {"uniform_random": _valid_record()})
    assert path.is_file()


def test_load_corrupt_json_returns_empty(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON 语法损坏时返回空字典并输出警告到 stderr。"""
    path = tmp_path / "scores.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_highscores(path) == {}
    assert "警告" in capsys.readouterr().err


def test_load_wrong_types_returns_empty(tmp_path: Path) -> None:
    """字段类型非法（score 为字符串）时跳过该条并警告。"""
    path = tmp_path / "scores.json"
    bad_record = _valid_record()
    bad_record["score"] = "100"
    path.write_text(json.dumps({"seven_bag_fixed": bad_record}), encoding="utf-8")
    assert load_highscores(path) == {}


def test_load_skips_only_invalid_record(tmp_path: Path) -> None:
    """单条纪录非法只跳过该条，其余模式正常加载。"""
    path = tmp_path / "scores.json"
    payload = {
        "seven_bag_fixed": _valid_record(score=100),
        "uniform_random": {"score": -1, "level": 1, "lines": 0, "date": "2026-08-15"},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_highscores(path)
    assert loaded.keys() == {"seven_bag_fixed"}


# ==================== 纪录构造与比较 ====================


def test_new_highscore_uses_today() -> None:
    """new_highscore 的日期取今天（ISO 格式）。"""
    record = new_highscore(score=50, level=1, lines=0)
    assert record.score == 50
    assert record.level == 1
    assert record.lines == 0
    assert record.date == date.today().isoformat()


def test_is_new_record_strict_greater() -> None:
    """只有严格大于才算破纪录，相等不算。"""
    current = HighScore(score=100, level=1, lines=0, date="2026-08-15")
    assert is_new_record(score=101, current=current) is True
    assert is_new_record(score=100, current=current) is False
    assert is_new_record(score=99, current=current) is False


# ==================== 模式键 ====================


def test_mode_key_combines_settings() -> None:
    """模式键由发牌模式与出生旋转组合。"""
    assert mode_key("seven_bag", False) == "seven_bag_fixed"
    assert mode_key("seven_bag", True) == "seven_bag_random"
    assert mode_key("uniform", True) == "uniform_random"
    assert mode_key("no_repeat", False) == "no_repeat_fixed"


# ==================== HighscoreStore ====================


def test_store_submit_returns_whether_new_record(tmp_path: Path) -> None:
    """首次提交破纪录返回 True，低分提交返回 False。"""
    store = HighscoreStore(path=tmp_path / "scores.json")
    assert store.submit("seven_bag_fixed", score=100, level=1, lines=0) is True
    assert store.submit("seven_bag_fixed", score=90, level=1, lines=0) is False
    assert store.get_highscore("seven_bag_fixed").score == 100


def test_store_records_per_mode_independent(tmp_path: Path) -> None:
    """不同模式键的纪录互不影响。"""
    store = HighscoreStore(path=tmp_path / "scores.json")
    store.submit("seven_bag_fixed", score=100, level=1, lines=0)
    store.submit("uniform_random", score=80, level=1, lines=0)
    assert store.get_highscore("seven_bag_fixed").score == 100
    assert store.get_highscore("uniform_random").score == 80


def test_store_missing_mode_returns_default(tmp_path: Path) -> None:
    """无纪录的模式返回全零默认 HighScore。"""
    store = HighscoreStore(path=tmp_path / "scores.json")
    default = store.get_highscore("seven_bag_fixed")
    assert default == HighScore(score=0, level=0, lines=0, date="")


def test_store_persists_across_instances(tmp_path: Path) -> None:
    """submit 落盘后，新建 Store 仍能读到该模式纪录。"""
    path = tmp_path / "scores.json"
    first = HighscoreStore(path=path)
    first.submit("no_repeat_random", score=150, level=2, lines=5)
    second = HighscoreStore(path=path)
    assert second.get_highscore("no_repeat_random").score == 150
