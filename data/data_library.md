# 数据库

每份数据一张卡片，目录如下：

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>数据源</th>
         <th nowrap>产品</th>
         <th nowrap>数据</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>Sharadar</td>
         <td nowrap>Sharadar Equity Prices</td>
         <td nowrap><a href="#sharadar_sep">SEP</a>、<a href="#sharadar_tickers">TICKERS</a>、<a href="#sharadar_actions">ACTIONS</a></td>
      </tr>
   </tbody>
</table>
</div>

## Sharadar

### 概览

<div style="overflow-x: auto;">
<table>
   <thead>
      <tr>
         <th nowrap>产品</th>
         <th nowrap>数据</th>
      </tr>
   </thead>
   <tbody>
      <tr>
         <td nowrap>Sharadar Core US Fundamentals Data</td>
         <td nowrap><code>SF1, DAILY, TICKERS, INDICATORS, ACTIONS, SP500, EVENTS</code></td>
      </tr>
      <tr>
         <td nowrap>Sharadar Core US Insiders Data</td>
         <td nowrap><code>SF2</code></td>
      </tr>
      <tr>
         <td nowrap>Sharadar Core US Institutional Investors Data</td>
         <td nowrap><code>SF3, SF3A, SF3B</code></td>
      </tr>
      <tr>
         <td nowrap>Sharadar Equity Prices</td>
         <td nowrap><code>SEP, ACTIONS, TICKERS, METRICS, INDICATORS</code></td>
      </tr>
      <tr>
         <td nowrap>Sharadar Fund Prices</td>
         <td nowrap><code>SFP, ACTIONS, TICKERS, METRICS, INDICATORS</code></td>
      </tr>
   </tbody>
</table>
</div>

### 数据卡片

<a id="sharadar_sep"></a>

<table>
   <tr>
      <th colspan="2" align="left">数据卡片 1：Sharadar SEP</th>
   </tr>
   <tr>
      <td nowrap><b>数据源</b></td>
      <td>Sharadar</td>
   </tr>
   <tr>
      <td nowrap><b>产品</b></td>
      <td>Sharadar Equity Prices</td>
   </tr>
   <tr>
      <td nowrap><b>一级资产类别</b></td>
      <td>股票 <code>EQ</code></td>
   </tr>
   <tr>
      <td nowrap><b>二级工具类型</b></td>
      <td>现货 <code>spot</code></td>
   </tr>
   <tr>
      <td nowrap><b>获取方式</b></td>
      <td>API</td>
   </tr>
   <tr>
      <td nowrap><b>数据字段</b></td>
      <td><code>ticker, date, open, high, low, close, volume, closeadj, closeunadj, lastupdated</code></td>
   </tr>
   <tr>
      <td nowrap><b>数据频率</b></td>
      <td>日频</td>
   </tr>
   <tr>
      <td nowrap><b>发布时间</b></td>
      <td>T 日收盘后</td>
   </tr>
</table>

<a id="sharadar_tickers"></a>

<table>
   <tr>
      <th colspan="2" align="left">数据卡片 2：Sharadar TICKERS</th>
   </tr>
   <tr>
      <td nowrap><b>数据源</b></td>
      <td>Sharadar</td>
   </tr>
   <tr>
      <td nowrap><b>产品</b></td>
      <td>Sharadar Equity Prices</td>
   </tr>
   <tr>
      <td nowrap><b>一级资产类别</b></td>
      <td>股票 <code>EQ</code></td>
   </tr>
   <tr>
      <td nowrap><b>二级工具类型</b></td>
      <td>现货 <code>spot</code></td>
   </tr>
   <tr>
      <td nowrap><b>获取方式</b></td>
      <td>API</td>
   </tr>
   <tr>
      <td nowrap><b>数据字段</b></td>
      <td><code>table, permaticker, ticker, name, exchange, isdelisted, category, cusips, siccode, sicsector, sicindustry, figi, famaindustry, sector, industry, scalemarketcap, scalerevenue, relatedtickers, currency, location, lastupdated, firstadded, firstpricedate, lastpricedate, firstquarter, lastquarter, secfilings, companysite</code></td>
   </tr>
   <tr>
      <td nowrap><b>数据频率</b></td>
      <td>快照</td>
   </tr>
   <tr>
      <td nowrap><b>发布时间</b></td>
      <td>未提供</td>
   </tr>
</table>

<a id="sharadar_actions"></a>

<table>
   <tr>
      <th colspan="2" align="left">数据卡片 3：Sharadar ACTIONS</th>
   </tr>
   <tr>
      <td nowrap><b>数据源</b></td>
      <td>Sharadar</td>
   </tr>
   <tr>
      <td nowrap><b>产品</b></td>
      <td>Sharadar Equity Prices</td>
   </tr>
   <tr>
      <td nowrap><b>一级资产类别</b></td>
      <td>股票 <code>EQ</code></td>
   </tr>
   <tr>
      <td nowrap><b>二级工具类型</b></td>
      <td>现货 <code>spot</code></td>
   </tr>
   <tr>
      <td nowrap><b>获取方式</b></td>
      <td>API</td>
   </tr>
   <tr>
      <td nowrap><b>数据字段</b></td>
      <td><code>date, action, ticker, name, value, contraticker, contraname</code></td>
   </tr>
   <tr>
      <td nowrap><b>数据频率</b></td>
      <td>事件</td>
   </tr>
   <tr>
      <td nowrap><b>发布时间</b></td>
      <td>未提供</td>
   </tr>
</table>
