# eblock

数据驱动的咖啡店模拟经营游戏（Python 学习项目）。

## 项目目标

以做游戏为载体，同时训练**游戏设计**与**软件工程**能力：数据驱动、类型明确、
分层解耦、测试与静态检查全绿。

详细学习计划见 [docs/plan.md](docs/plan.md)。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| `docs/` | 所有文档类文件（计划、规范、索引） |
| `src/eblock/sim/` | 纯逻辑层：经济模拟（零 Pygame 依赖） |
| `src/eblock/ui/` | 渲染与输入层 |
| `src/eblock/app/` | 装配层与主循环 |
| `src/eblock/save/` | 存档层：GameState ↔ JSON |
| `config/` | 玩法数值 JSON（配方、价格、事件等） |
| `scripts/` | 自动挂机模拟等开发脚本 |
| `saves/` | 运行时生成的存档（不入库） |
| `tests/` | pytest 测试 |

## 文件管理规范

- 所有文档类文件统一放在 `docs/`，文件名用英文小写加连字符。
- 玩法数值一律放 `config/`，代码内禁止硬编码游戏数值。
- 游戏代码按 sim / ui / app / save 分层，依赖方向只允许向下。
- 开发脚本放 `scripts/`，测试放 `tests/`。

## 开发环境

- Python >= 3.12
- 工具链：ruff（lint + format）、mypy --strict（类型检查）、pytest（测试）

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## 提交门槛

每次里程碑提交前必须全绿：

```powershell
ruff check .
ruff format --check .
mypy src
pytest
```

## 开发进度

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 0 | [俄罗斯方块热身游戏](docs/tetris-warmup.md) | 未开始 |
| 1 | 控制台版核心循环 | 未开始 |
| 2 | GUI 完整版 | 未开始 |
| 3 | 数值平衡与打磨 | 未开始 |
| 4 | 第二作（可选） | 未开始 |

## License

MIT
