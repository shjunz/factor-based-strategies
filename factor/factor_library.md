# 因子库

每条因子一张卡片，目录如下：

| 因子编号 |
|---|
| [`MOM_001`](#mom_001) |

<a id="mom_001"></a>

<table>
   <tr>
      <th colspan="2" align="left">因子卡片 1：旗帜形态</th>
   </tr>
   <tr>
      <td nowrap><b>因子编号</b></td>
      <td><code>MOM_001</code></td>
   </tr>
   <tr>
      <td nowrap><b>计算公式</b></td>
      <td>
         <code>J_min &lt;= j &amp;&amp; k &lt;= K_max &amp;&amp; RunUp &gt;= R_min &amp;&amp; HigherLow &gt; 0 &amp;&amp; Tight &lt; 1 ? 1 : 0</code><br><br>
         <code>k = ts_argmax(close_adj, L)</code><br>
         <code>j = ts_argmin(close_adj, k + 1)</code><br>
         <code>RunUp = delay(close_adj / ts_min(close_adj, 15) - 1, k)</code><br>
         <code>Retain = ts_min(close_adj, k + 1) / delay(close_adj, k)</code><br>
         <code>HigherLow = ts_spearman(low, ts_step(1), j + 1)</code><br>
         <code>Tight = ts_mean(log(high / low), 5) / delay(ts_mean(log(high / low), j + 1 - 5), 5)</code>
      </td>
   </tr>
   <tr>
      <td nowrap><b>经济逻辑</b></td>
      <td>短期大涨后，价格出现浅回调，随后在低点逐步抬高、且振幅逐步收窄的状态下盘整，说明大涨反映的是市场尚未充分消化的新信息，价格将迎来下一段上涨</td>
   </tr>
   <tr>
      <td nowrap><b>预期方向</b></td>
      <td>正</td>
   </tr>
   <tr>
      <td nowrap><b>所用数据</b></td>
      <td><code>close_adj</code>、<code>high</code>、<code>low</code></td>
   </tr>
   <tr>
      <td nowrap><b>参数</b></td>
      <td>
         <code>L</code> = 63 根 bar，回看窗口<br>
         <code>J_min</code> = 10 根 bar，盘整的最短长度<br>
         <code>K_max</code> = 42 根 bar，回调加盘整的最长长度<br>
         <code>R_min</code> = 0.3，大涨的最小幅度
      </td>
   </tr>
   <tr>
      <td nowrap><b>来源文献</b></td>
      <td>Qullamaggie 突破形态</td>
   </tr>
   <tr>
      <td nowrap><b>负责人</b></td>
      <td>shjunz</td>
   </tr>
</table>
