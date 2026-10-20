# Architecture

本文件只把 research_spec.md 的章节映射到代码文件，每个文件一行。方法看 research_spec.md，实现细节看各文件的 docstring。改动顺序：先改本文件，再写代码。

## 约定

- 存储：面板数据为长表，一行一个 (timestamp, symbol)；所有表都存 parquet。

## M3 — 因子评价（eval/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `bars.py` | M3.1 | 基础频率 | 原始 bar 合成基础 bar、缺失标记 |
| `factors.py` | M3.2 | 因子值 | 异常值修正、空缺值处理、分布调整、因子中性化 |
| `returns.py` | M3.3 | 未来收益率 | 收益率口径、跨市场对齐 |
| `metrics.py` | M3.4 | 因子评价指标 | 主指标：Rank IC、分层价差；方向判断：反向检验、U 形检验；副指标：IC 衰减、分层 CVaR、分层换手率、分层净值、分层夏普率、分层最大回撤、因子风险画像 |
| `segment.py` | M3.5 | 样本内划分 | 按期切分 |
| `scope.py` | M3.6 | 指标范围 | 全样本计算、按期计算 |
| `pipeline.py` | M3 | 流程 | 串起 M3.1–M3.6 |

## M4 — 因子组合（model/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `score.py` | M4.1 | 因子综合评分 | 显著性、属性计算、属性合成、综合评分 |
| `selection.py` | M4.2 | 因子选择 | 因子排名、因子互补性、因子交易表现 |
| `standardize.py` | M4.3 | 因子值标准化 | Gauss-rank、z-score |
| `label.py` | M4.4 | 未来收益率调整 | 均值调整、波动率调整、Gauss-rank、z-score |
| `models.py` | M4.5 | 模型选择 | 等权加法、Ridge Regression、XGBoost、Transformer |
| `missing.py` | M4.6 | 数据处理 | 各模型的缺失值处理 |
| `train_model.py` | M4.7 | 模型训练 | 训练目标、训练轮数、选择超参数与模型 |
| `eval_model.py` | M4.8 | 模型检验 | 在 OOS Test 上评价一次，与等权加法对比 |
| `pipeline.py` | M4 | 流程 | 串起 M4.1–M4.8 |
