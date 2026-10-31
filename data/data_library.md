# 数据库

每个数据源一张卡片，每张表一行。

## 数据卡片 1：Sharadar

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>一级资产类别</th>
         <th nowrap>二级工具类型</th>
         <th nowrap>获取方式</th>
         <th nowrap>数据字段</th>
         <th nowrap>数据频率</th>
         <th nowrap>发布时间</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>股票 <code>EQ</code></td>
         <td nowrap>现货 <code>spot</code></td>
         <td nowrap>API：<code>SHARADAR/SEP</code></td>
         <td nowrap><code>ticker, date, open, high, low, close, volume, closeadj, closeunadj, lastupdated</code></td>
         <td nowrap>日频</td>
         <td nowrap>T 日收盘后</td>
      </tr>
      <tr>
         <td nowrap>股票 <code>EQ</code></td>
         <td nowrap>现货 <code>spot</code></td>
         <td nowrap>API：<code>SHARADAR/TICKERS</code></td>
         <td nowrap><code>table, permaticker, ticker, name, exchange, isdelisted, category, cusips, siccode, sicsector, sicindustry, figi, famaindustry, sector, industry, scalemarketcap, scalerevenue, relatedtickers, currency, location, lastupdated, firstadded, firstpricedate, lastpricedate, firstquarter, lastquarter, secfilings, companysite</code></td>
         <td nowrap>快照</td>
         <td nowrap>未提供</td>
      </tr>
      <tr>
         <td nowrap>股票 <code>EQ</code></td>
         <td nowrap>现货 <code>spot</code></td>
         <td nowrap>API：<code>SHARADAR/ACTIONS</code></td>
         <td nowrap><code>date, action, ticker, name, value, contraticker, contraname</code></td>
         <td nowrap>事件</td>
         <td nowrap>未提供</td>
      </tr>
   </tbody>
</table>
</div>
