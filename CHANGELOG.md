# Changelog

所有重要的專案變更都會記錄在此。

格式基於 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)

---

## [0.3.0] - 2025-12-05

### Added
- 做空交易支援 (Short Selling)
- 槓桿交易 (Leverage 1-100x)
- 方向感知的 SL/TP (Direction-aware Stop Loss / Take Profit)
- 策略註冊系統 (Strategy Registry)
- 批量回測引擎 (Portfolio Runner)
- 文本報表生成器 (Text Reporter)
- 命令行介面 (CLI)
- YAML 配置支援

### Changed
- Broker: `buy()` / `sell()` 語義變更（支援做空）
- Engine: `_check_sl_tp()` 增加 direction 參數
- Trade: 新增 `direction` 和 `leverage` 字段

### Fixed
- 浮點數精度問題（broker 資金檢查）
- 空單平倉邏輯錯誤

---

## [v0.2.0] - 2024-12-03

### 新增
- Position Sizer 系統
  - `AllInSizer`：全倉進出（v0.1 行為）
  - `FixedCashSizer`：固定金額投入
  - `PercentOfEquitySizer`：固定比例投入
- 停損停利（SL/TP）功能
  - 使用 high/low 盤中觸發
  - 支援固定百分比設定
  - SL 與 TP 同時觸發時，停損優先
- 完整 Trade Log（DataFrame）
  - 新增欄位：entry_reason, exit_reason, holding_bars, mae, mfe
  - 每筆交易完整記錄進出場資訊
- Metrics 2.0
  - 新增：profit_factor, avg_win, avg_loss, win_loss_ratio, expectancy
  - 新增：max_consecutive_win, max_consecutive_loss
  - 加入邊界條件保護（除零、無交易等情況）

### 修正
- 修正 Position Sizer size <= 0 時的行為（不進場）
- 修正 SL/TP 觸發邏輯（使用 low/high 而非 close）

### 測試
- 新增 35 個測試案例
- 涵蓋 Position Sizer、SL/TP、Trade Log、Metrics
- 所有 v0.1 測試保持通過（向後兼容）

### 文件
- 更新所有技術規格
- 記錄設計決策於 DECISIONS.md

---

## [v0.1.0] - 2024-11-20

### 新增
- MVP 回測引擎
  - 基礎回測流程（`run_backtest`）
  - 模擬交易所（`SimulatedBroker`）
  - 策略基底類別（`BaseStrategy`）
- 資料模組
  - CSV 載入與驗證（`data/storage.py`）
  - OHLCV 格式檢查（`data/validator.py`）
  - Binance 資料下載（`data/fetcher.py`）
- 基礎 Metrics
  - total_return, max_drawdown, num_trades, win_rate, avg_trade_return
- 示範策略
  - SimpleSMA 均線交叉策略
- 測試模組
  - 核心功能單元測試

### 測試成果
- 測試資料：BTCUSDT 1h（約 700 根 K 線）
- 交易次數：約 47 筆
- 勝率：約 27%
- 總報酬：約 20%
- 最大回撤：約 -8%

---

## [Unreleased]

### 規劃中
準備中
