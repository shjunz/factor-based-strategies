---
paths:
  - "**/*.py"
---

# Code Style Guide

## 1. Names

- 常量按大写命名，单词之间用下划线连接。

  例如：

  ```python
  DATA_DIR = Path(__file__).resolve().parents[3] / "data"
  SORT_KEYS = ["ticker", "date"]
  ```

- 函数、变量和模块按小写命名，单词之间用下划线连接。

  例如：

  ```python
  from fbs.backtesting.sample_split import split_segments
  ```

- 类和异常按大驼峰命名。

  例如：

  ```python
  class OrderRecord:
      ...

  raise FileExistsError(path)
  ```

## 2. Imports

- 导入写在 `# Imports` 单元里，按标准库、第三方库、本地模块的顺序分成三组，组与组之间空一行。每组内先写 `import x`，再写 `from x import y`，两类各自按模块名的字母顺序排列。

  例如：

  ```python
  # %%
  # Imports
  import json
  from dataclasses import asdict
  from datetime import datetime, timedelta
  from zoneinfo import ZoneInfo

  import pandas as pd

  from fbs.live.brokers import make_broker
  from fbs.live.loader import load_strategy
  ```

- 特殊格式的导入按以下规定写：

  - 通用缩写：用 `as` 改成业界通用的缩写。

    例如：

    ```python
    import numpy as np
    import pandas as pd
    ```

  - 避开名字冲突：和已有的名字重名时，用 `as` 改名。

    例如：

    ```python
    import time as clock_time
    from datetime import datetime, time
    ```

## 3. Docstrings

- 模块摘要写在文件开头，开头和结尾的 `"""` 各自单独占一行，摘要行写成 `<文件名> - <摘要>.`。摘要内容保持简短，描述本模块，名词短语或动词开头都可以，动词开头的用祈使句。`__init__.py` 不用写。

  例如：

  ```python
  """
  extract.py - Download and read data from Sharadar products on Nasdaq Data Link.
  """
  ```

- 函数摘要写在 `def` 下一行，开头和结尾的 `"""` 各自单独占一行，摘要行写成一句清楚准确的话，名词短语或动词开头都可以，动词开头的用祈使句。
  例如：

  ```python
  def rank_ic(signal, fwd_ret):
      """
      Spearman correlation between signal and forward return.
      ...
      """

  def add_instrument_id(raw, tickers, table):
      """
      Add instrument IDs to Sharadar raw data by permaticker.
      ...
      """
  ```

- `pd.DataFrame` 写成 `<值>. Index = <index>, Columns = <columns>.`。宽表和长表都要写全 Index 和 Columns，`Columns =` 后的多项只用逗号连接。

  例如：

  ```python
  def pivot_close(prices):
      """
      ...
      Parameters
      ----------
      prices : pd.DataFrame
          Prices. Index = row number, Columns = ticker, date, close.

      Returns
      -------
      wide : pd.DataFrame
          Close prices. Index = date, Columns = ticker.
      """
  ```

- `pd.Series` 写成 `<值> per <index>.`，和长表逐行对齐的写成 `<值> per row.`。

  例如：

  ```python
  def rank_ic(signal, fwd_ret):
      """
      ...
      Returns
      -------
      rankic : pd.Series
          Rank IC per timestamp.
      ...
      """

  def map_date_timestamps(dates, calendar):
      """
      ...
      Returns
      -------
      timestamps : pd.Series
          UTC close timestamp per row.
      ...
      """
  ```

- `bool` 结果写成 `True if <condition>.`，开关参数写成 `True to <action>.`。

  例如：

  ```python
  def u_shape_check(buckets):
      """
      ...
      Returns
      -------
      u_shape_flag : bool
          True if the factor is U-shaped or inverted U-shaped.
      ...
      """

  def download_table(table, path, /, columns=None, overwrite=False, **filters):
      """
      ...
      Parameters
      ----------
      ...
      overwrite : bool
          True to replace an existing file at `path`.
      ...
      """
  ```

- 抛出异常里每种异常类型占一行，条件写成 `If <condition>.`。

  例如：

  ```python
  def pivot_close(prices):
      """
      ...
      Raises
      ------
      ValueError
          If a column is missing.
          If (ticker, date) is not unique.
      """
  ```

## 4. Comments

- 注释写代码做了什么，简洁清晰即可。

  例如：

  ```python
  # Stop if the file already exists
  if path.exists() and not overwrite:
      raise FileExistsError(path)
  ```

- 注释和它的代码之间不空行。

  例如：

  ```python
  # Create the parent directories if they don't exist
  path.parent.mkdir(parents=True, exist_ok=True)
  ```

## 5. Cells

- 单元里只有一块代码时，`# %%` 下一行写一句注释，直接写代码。

  例如：

  ```python
  # %%
  # Sharadar table download
  def download_table(table, path, /, columns=None, overwrite=False, **filters):
      ...
  ```

- 单元里有多块代码时，`# %%` 下一行先写标题，空行后再在每块代码上方各写一行注释。

  例如：

  ```python
  # %%
  # Bronze Path

  # File-name text of a single filter value: dates as YYYYMMDD
  def _scalar(value):
      ...

  # File-name text of a filter: a range as start-end, a list joined by commas
  def _filter_token(value):
      ...
  ```

## 6. Functions

- 函数写成 `def <函数名>(<参数>):`，下面紧接 docstring，参数和返回值的类型写在 docstring 的 Parameters 和 Returns 里。

  例如：

  ```python
  def pivot_close(prices):
      """
      ...
      Parameters
      ----------
      prices : pd.DataFrame
          Prices. Index = row number, Columns = ticker, date, close.

      Returns
      -------
      wide : pd.DataFrame
          Close prices. Index = date, Columns = ticker.
      """
  ```

- 特殊格式的函数按以下规定写：

  - 接口类（`typing.Protocol`）的方法：所有参数和返回值都写类型注解，没有返回值的写 `-> None`，完整的 docstring 写在实现这个接口的类里。

  例如：

  ```python
  class Broker(Protocol):
      ...
      def positions(self) -> dict[str, int]:
          """
          Shares held per symbol, negative for shorts.
          """

      def cancel_all(self) -> None:
          """
          Cancel every open order in the account.
          """
  ```
