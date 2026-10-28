# 数据源

本文件帮助读者了解我们有哪些数据源、各能下载什么，每个数据源一张卡片，格式见 [research_spec.md M1.1.2](../research_spec.md#m112-数据源)。分类取值与形态见 [M1.1.1](../research_spec.md#m111-原始数据)，形态特有处理见 [M1.2.3](../research_spec.md#m123-形态特有处理)。

- **用途**：收益数据（计算可交易收益）/ 特征数据（构建或评价因子），括号内为补充说明。
- **数据频率**：当前版本只支持日频及以上；日内数据登记在文末"暂不纳入"。
- **可用时间**：数据最早可用于决策的时点（UTC），用于 [M1.2.4](../research_spec.md#m124-数据对齐) point-in-time 约束。标"待确认"的需在接入时核实。
- **是否修订 / 是否提供历史版本**：数据源是否会回溯修订已发布的值、是否提供各版本的发布时间，决定修订版本 `available_at` 的取法，见 [M1.2.4.1](../research_spec.md#m1241-数据修订)。

## 数据存储

按 [M1.3.1](../research_spec.md#m131-本地云端存储) 分三层存放（`{分类}` = `{一级资产类别}/{二级业务类别}/{频率}`）：

- **数据字典**：`data/dictionary/data_dictionary.csv`（每个形态一行），纳入 git，格式见 [M1.3.3](../research_spec.md#m133-数据字典格式)
- **原始数据**：`data/extraction/{分类}/`
- **中间数据**：`data/transform/{步骤}/{分类}/`
- **最终数据**：`data/loading/{分类}/`（不按 IS / OOS 拆分，见 [M1.3.4](../research_spec.md#m134-研究样本划分is--oos)），格式见 [M1.3.2](../research_spec.md#m132-loading-文件格式)

云端（地址询问 Liangxiao LI）仅保存 `extraction/` 与 `loading/`，见 [M1.3.1](../research_spec.md#m131-本地云端存储)。

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>项目</th>
         <th nowrap>规则</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>Loading 收益数据文件命名</td>
         <td nowrap><code>{一级资产类别}_{二级业务类别}_收益_{形态}_{清洗日期}</code></td>
      </tr>
      <tr>
         <td nowrap>Loading 特征数据文件命名</td>
         <td nowrap><code>{一级资产类别}_{二级业务类别}_特征_{形态}_{清洗日期}</code></td>
      </tr>
      <tr>
         <td nowrap>Loading 收益数据列</td>
         <td nowrap><code>date, instrument_id, form, asset_class, category, ret, tradable, quality_flag, available_at</code>（价格 / 报价等可选列见 M1.3.2.2）</td>
      </tr>
      <tr>
         <td nowrap>Loading 特征数据列</td>
         <td nowrap><code>date, instrument_id, field_id, form, data_category, value, frequency, quality_flag, available_at</code></td>
      </tr>
   </tbody>
</table>
</div>

## 数据源卡片 1：EODHD

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>用途</th>
         <th nowrap>一级资产类别</th>
         <th nowrap>二级业务类别</th>
         <th nowrap>形态</th>
         <th nowrap>数据接口</th>
         <th nowrap>可下载字段</th>
         <th nowrap>数据频率</th>
         <th nowrap>可用时间</th>
         <th nowrap>是否修订</th>
         <th nowrap>是否提供历史版本</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>收益数据</td>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>EOD Historical Data API</td>
         <td nowrap>日期；开盘价；最高价；最低价；收盘价；成交量；复权收盘价</td>
         <td nowrap>日频；周频 / 月频聚合</td>
         <td nowrap>T 日美股收盘后（收盘 21:00 UTC，夏令时 20:00 UTC）；供应商更新延迟待确认</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>收益数据（复权）/ 特征数据（公司行为）</td>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Dividends &amp; Splits API</td>
         <td nowrap>除息日；宣告日（可选）；登记日（可选）；支付日（可选）；分红金额；未调整分红金额；分红币种（可选）；拆股生效日；拆股比例</td>
         <td nowrap>公司行动事件</td>
         <td nowrap>复权：除息日 / 生效日；公司行为事件：宣告日（UTC 时点待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（基本面；行业分类）</td>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Fundamentals API</td>
         <td nowrap>流通股本；总股本；市值；行业分类；财务报表（利润表、资产负债表、现金流量表，含报告期与披露日）</td>
         <td nowrap>季度 / 年度；股本按更新</td>
         <td nowrap>财务数据：披露日之后（不能用报告期）；股本：更新日之后</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>收益数据（证券目录、退市补全）</td>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Exchange Symbols API（含退市列表）</td>
         <td nowrap>证券代码；名称；交易所；国家；交易货币；证券类型；ISIN（部分证券缺失）；是否退市</td>
         <td nowrap>证券目录快照</td>
         <td nowrap>当前快照，不是 point-in-time 数据，不能直接作为历史资产池</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（隐含波动率曲面；映射到标的股票）</td>
         <td nowrap>股票</td>
         <td nowrap>衍生品</td>
         <td nowrap></td>
         <td nowrap>US Stock Options Data API</td>
         <td nowrap>合约代码；标的代码；到期日；行权价；认购 / 认沽标记；买价；卖价；成交价；成交量；未平仓量；隐含波动率；Delta；Gamma；Theta；Vega</td>
         <td nowrap>日频（美股期权 EOD；独立产品 / 套餐权限）</td>
         <td nowrap>T 日美股收盘后（收盘 21:00 UTC，夏令时 20:00 UTC）；供应商更新延迟待确认</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（收益率曲线）</td>
         <td nowrap>固定收益</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>GBOND / EOD Historical Data API</td>
         <td nowrap>政府债券收益率：日期；开盘；最高；最低；收盘；复权收盘（均为收益率，不是价格）</td>
         <td nowrap>日频；按国家及期限</td>
         <td nowrap>T 日各国市场收盘后（UTC 时点按市场换算，待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（资金利率；无风险利率）</td>
         <td nowrap>固定收益</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Interest Rates API / Reference Rates</td>
         <td nowrap>日期；代码；币种；利率类型；利率；来源；来源序列代码；百分位数（部分序列）；成交额（部分序列）</td>
         <td nowrap>日频</td>
         <td nowrap>源端发布后 T+1（UTC 时点待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（资金压力）</td>
         <td nowrap>固定收益</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Funding Stress Spreads API</td>
         <td nowrap>资金压力利差：日期；代码；利差值；计算公式；两端利率代码及数值</td>
         <td nowrap>日频</td>
         <td nowrap>源端发布后 T+1（UTC 时点待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（EURIBOR；收益率曲线）</td>
         <td nowrap>固定收益</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>MONEY / EOD Historical Data API</td>
         <td nowrap>EURIBOR；政府债券收益率曲线；日期；开盘；最高；最低；收盘；复权收盘</td>
         <td nowrap>日频</td>
         <td nowrap>按源端发布时间（UTC 时点待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>收益数据</td>
         <td nowrap>外汇</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>FOREX / EOD Historical Data API</td>
         <td nowrap>日期；开盘价；最高价；最低价；收盘价；成交量（供应商字段，不是全市场集中成交量，不作为因子输入）</td>
         <td nowrap>日频</td>
         <td nowrap>供应商切日时点之后（切日时点待确认，见 M1.2.4）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（央行政策利率；外汇 carry）</td>
         <td nowrap>外汇</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Interest Rates API / Policy Rates</td>
         <td nowrap>日期；代码；国家；央行；利率；来源；来源序列代码</td>
         <td nowrap>政策决议频率；工作日刷新</td>
         <td nowrap>源端发布后 T+1（UTC 时点待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>收益数据（货币对目录；收益交叉校验）</td>
         <td nowrap>外汇</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>MONEY / Exchange Symbols API</td>
         <td nowrap>货币对代码；名称；交易货币；ECB / Norges Bank 参考汇率</td>
         <td nowrap>货币对目录；参考汇率按日发布</td>
         <td nowrap>参考汇率：源端发布后（ECB 约 16:00 CET，待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
      <tr>
         <td nowrap>特征数据（现货参考价格）</td>
         <td nowrap>大宗商品</td>
         <td nowrap>衍生品</td>
         <td nowrap></td>
         <td nowrap>Commodities Historical API</td>
         <td nowrap>日期；数值；序列名称；单位；频率</td>
         <td nowrap>日频、周频、月频、季频或年频，依具体序列</td>
         <td nowrap>按序列发布时间（UTC 时点待确认）</td>
         <td nowrap>待确认</td>
         <td nowrap>待确认</td>
      </tr>
   </tbody>
</table>
</div>

**暂不纳入**（日内数据，当前版本不支持）：

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>一级资产类别</th>
         <th nowrap>二级业务类别</th>
         <th nowrap>形态</th>
         <th nowrap>数据接口</th>
         <th nowrap>可下载字段</th>
         <th nowrap>数据频率</th>
         <th nowrap>可用时间</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Intraday Historical Data API</td>
         <td nowrap>时间戳；开盘价；最高价；最低价；收盘价；成交量</td>
         <td nowrap>1 分钟；5 分钟；1 小时</td>
         <td nowrap>bar 结束后（延迟依套餐）</td>
      </tr>
      <tr>
         <td nowrap>外汇</td>
         <td nowrap>现货</td>
         <td nowrap></td>
         <td nowrap>Intraday Historical Data API</td>
         <td nowrap>时间戳；开盘价；最高价；最低价；收盘价；成交量</td>
         <td nowrap>1 分钟；5 分钟；1 小时</td>
         <td nowrap>bar 结束后</td>
      </tr>
   </tbody>
</table>
</div>

## 数据源卡片 2：Sharadar

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>一级资产类别</th>
         <th nowrap>二级业务类别</th>
         <th nowrap>数据接口</th>
         <th nowrap>可下载字段</th>
         <th nowrap>数据频率</th>
         <th nowrap>可用时间</th>
         <th nowrap>是否修订</th>
         <th nowrap>是否提供历史版本</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap>Nasdaq Data Link，<code>SHARADAR/SEP</code> 整表导出</td>
         <td nowrap>代码；日期；开盘价；最高价；最低价；收盘价；成交量（以上为拆股复权）；复权收盘价（拆股、分红、分拆复权）；未复权收盘价；最后更新日</td>
         <td nowrap>日频</td>
         <td nowrap>T 日美股收盘后（收盘 21:00 UTC，夏令时 20:00 UTC）；供应商更新延迟待确认</td>
         <td nowrap>是：拆股、分红后，历史复权价格会回溯重算</td>
         <td nowrap>否：整表导出只有当前版本</td>
      </tr>
      <tr>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap>Nasdaq Data Link，<code>SHARADAR/TICKERS</code> 整表导出</td>
         <td nowrap>所属表；永久代码；代码；名称；交易所；是否退市；类别；CUSIP；SIC 代码、板块、行业；FIGI；Fama 行业；板块；行业；市值规模；营收规模；关联代码；币种；所在地；最后更新日；首次收录日；首个 / 最后价格日；首个 / 最后财报季度；SEC 文件链接；公司网站</td>
         <td nowrap>快照</td>
         <td nowrap>当前快照，不是 point-in-time；行业、交易所等为最新值</td>
         <td nowrap>是：快照每日更新</td>
         <td nowrap>否</td>
      </tr>
      <tr>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap>Nasdaq Data Link，<code>SHARADAR/ACTIONS</code> 整表导出</td>
         <td nowrap>日期；行为类型；代码；名称；数值；对手方代码；对手方名称</td>
         <td nowrap>公司行为事件</td>
         <td nowrap>生效日；公告日数据源未提供</td>
         <td nowrap>待确认</td>
         <td nowrap>否：整表导出只有当前版本</td>
      </tr>
   </tbody>
</table>
</div>

## 覆盖缺口

以下 M1.1.1 中的数据尚无已登记的数据源：

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>一级资产类别</th>
         <th nowrap>二级业务类别</th>
         <th nowrap>缺少的数据</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>股票</td>
         <td nowrap>衍生品</td>
         <td nowrap>股指期货：收益数据；期货基差、期限结构、持仓量、COT、VIX</td>
      </tr>
      <tr>
         <td nowrap>股票</td>
         <td nowrap>现货</td>
         <td nowrap>上市普通股：分析师预期、指数成分与权重（历史版本）、融券余额、资金流、新闻情绪</td>
      </tr>
      <tr>
         <td nowrap>固定收益</td>
         <td nowrap>现货</td>
         <td nowrap>公司债：收益数据；信用利差、信用评级</td>
      </tr>
      <tr>
         <td nowrap>固定收益</td>
         <td nowrap>衍生品</td>
         <td nowrap>国债期货、短期利率期货、利率互换、CDS：收益数据；CTD 与隐含回购利率、互换利差、CDS 利差期限结构</td>
      </tr>
      <tr>
         <td nowrap>外汇</td>
         <td nowrap>衍生品</td>
         <td nowrap>外汇远期、NDF、外汇掉期：收益数据；远期点数、交叉货币基差、外汇期权隐含波动率</td>
      </tr>
      <tr>
         <td nowrap>大宗商品</td>
         <td nowrap>衍生品</td>
         <td nowrap>商品期货：收益数据；期限结构、库存、COT、供需报告</td>
      </tr>
      <tr>
         <td nowrap>跨资产</td>
         <td nowrap>—</td>
         <td nowrap>宏观经济（GDP、CPI、PMI、就业）、经济 / 事件日历、风险因子数据（M3.4 需要）</td>
      </tr>
   </tbody>
</table>
</div>
