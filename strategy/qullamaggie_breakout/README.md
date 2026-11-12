# qullamaggie_breakout

本文档记录这次研究选用的方法与参数，各方法的定义见 `research_spec.md` 对应章节。

## 研究问题

本研究复现 Qullamaggie 的突破进场策略。该策略是规则型策略，转为因子研究时，先拆出交易者所看形态背后的经济逻辑，写成可检验的假设，再用因子度量这些假设。

## M1 数据ETL

**数据源**：Sharadar 的 `SEP` 与 `TICKERS`

**读取区间**：2015-01-01 至 2026-10-28

## M2 因子库

**因子编号**：`MOM_001`

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

## M4.1.2 因子预处理

**空缺值处理**：有效数量，`N_min` = 30
