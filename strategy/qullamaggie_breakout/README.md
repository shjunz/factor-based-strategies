# qullamaggie_breakout

本文档记录这次研究选用的方法与参数，各方法的定义见 `research_spec.md` 对应章节。

## 研究问题

本研究复现 Qullamaggie 的突破进场策略。该策略是规则型策略，转为因子研究时，先拆出交易者所看形态背后的经济逻辑，写成可检验的假设，再用因子度量这些假设。

## M1 数据ETL

**数据源**：Sharadar 的 `SEP` 与 `TICKERS`

**清洗数据**：

**读取区间**：2015-01-01 至 2026-10-28

## M2 因子库

**因子编号**：`MOM_001`、`MOM_002`、`VOL_001`、`LIQ_001`

## M3.1 资产集

每个时间点同时满足以下条件的标的入选：

**证券类型**：`category` 为 `Domestic Common Stock` 或 `Domestic Common Stock Primary Class`

**上市场所**：`exchange` 为 `NYSE`、`NASDAQ` 或 `NYSEMKT`

**价格**：`close_raw` 不低于 5 美元

**波动**：过去 20 个交易日 ADR 不低于 ，ADR 为每日 `high / low − 1` 的平均值

**流动性**：过去 20 个交易日日均成交额不低于 ，日均成交额为每日 `close` 与 `volume` 之积的平均值

每个时间点只用当时及之前的数据判断是否入选，未入选标的的数据照常保留。

## M3.2 样本划分

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>分区</th>
         <th nowrap>区间</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>IS</td>
         <td nowrap>2016-01-01 至 2022-12-31</td>
      </tr>
      <tr>
         <td nowrap>Embargo</td>
         <td nowrap>2023-01-01 至 2023-01-31</td>
      </tr>
      <tr>
         <td nowrap>OOS</td>
         <td nowrap>2023-02-01 至 2026-10-28</td>
      </tr>
   </tbody>
</table>
</div>

OOS 的结果只做报告，不用于调整任何设定。

## M4.1.1 因子值

**计算频率**：日频，每个交易日都计算因子值

**历史不足**：回看窗口内的交易日不足时，因子值为 NaN

## M4.1.2 因子预处理

**因子描述统计**：全部统计量

**异常值修正**：中位数法

**空缺值处理**：覆盖率，`θ_cov` = 0.8

## M4.1.3 调仓频率

周度，调仓日为每周最后一个交易日。

## M4.1.4 未来收益率

第 t 个调仓日收盘到第 t+1 个调仓日收盘的 `close_adj` 收益率。

## M4.1.5 样本内分组

**按期分组**：`L_seg` = 1 年，`P` = 7

## M4.1.6 因子评价指标

**显著性检验**：Newey-West HAC

**主指标**：Rank IC、分层价差（`K` = 5，`θ_win` = 0.01）、Fama-MacBeth 回归

**方向判断**：反向检验、U 形检验

**副指标**：IC 衰减（`H` = 6）、分层 CVaR（`θ_CVaR` = 0.05）、分层换手率、分层净值、分层夏普率、分层最大回撤

IC 衰减只用未来收益率窗口完全落在 IS 内的调仓日。
