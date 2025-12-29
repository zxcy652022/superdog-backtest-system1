"""
Binance Futures Broker v1.0

幣安永續合約實盤交易 Broker

功能:
- 連接幣安 USDT-M 永續合約 API
- 下單、平倉、查詢持倉
- 查詢餘額、K線數據
- 設定槓桿、保證金模式

設計原則:
- 與 SimulatedBroker 接口盡量一致
- 所有操作都有錯誤處理
- 支援逐倉/全倉模式

Version: v1.0
"""

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlencode

import requests

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 幣安 API 端點
BINANCE_FUTURES_BASE = "https://fapi.binance.com"
BINANCE_FUTURES_TESTNET = "https://testnet.binancefuture.com"


@dataclass
class Position:
    """持倉資訊"""

    symbol: str
    side: Literal["LONG", "SHORT", "BOTH"]
    qty: float
    entry_price: float
    unrealized_pnl: float
    leverage: int
    margin_type: Literal["cross", "isolated"]


@dataclass
class OrderResult:
    """下單結果"""

    order_id: int
    symbol: str
    side: str
    type: str
    qty: float
    price: float
    status: str
    executed_qty: float
    avg_price: float


class BinanceFuturesBroker:
    """幣安永續合約 Broker"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
    ):
        """
        初始化 Broker

        Args:
            api_key: API Key（可從環境變數讀取）
            api_secret: API Secret（可從環境變數讀取）
            testnet: 是否使用測試網
        """
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise ValueError("API Key 和 Secret 必須提供（或設定環境變數）")

        self.base_url = BINANCE_FUTURES_TESTNET if testnet else BINANCE_FUTURES_BASE
        self.testnet = testnet
        self.recv_window = 5000  # 請求有效時間窗口 (ms)

    # === 簽名與請求 ===

    def _sign(self, params: Dict[str, Any]) -> str:
        """生成 HMAC SHA256 簽名"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return signature

    def _get_timestamp(self) -> int:
        """取得當前時間戳 (毫秒)"""
        return int(time.time() * 1000)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        發送 API 請求

        Args:
            method: HTTP 方法 (GET/POST/DELETE)
            endpoint: API 端點
            params: 請求參數
            signed: 是否需要簽名

        Returns:
            API 回應
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}
        params = params or {}

        if signed:
            params["timestamp"] = self._get_timestamp()
            params["recvWindow"] = self.recv_window
            params["signature"] = self._sign(params)

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, params=params, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=10)
            else:
                raise ValueError(f"不支援的 HTTP 方法: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求失敗: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"回應內容: {e.response.text}")
            raise

    # === 帳戶資訊 ===

    def get_account_balance(self) -> Dict[str, float]:
        """
        取得帳戶餘額

        Returns:
            {'total': 總餘額, 'available': 可用餘額, 'unrealized_pnl': 未實現盈虧}
        """
        data = self._request("GET", "/fapi/v2/balance", signed=True)

        # 找到 USDT 餘額
        for asset in data:
            if asset["asset"] == "USDT":
                return {
                    "total": float(asset["balance"]),
                    "available": float(asset["availableBalance"]),
                    "unrealized_pnl": float(asset["crossUnPnl"]),
                }

        return {"total": 0.0, "available": 0.0, "unrealized_pnl": 0.0}

    def get_account_info(self) -> Dict[str, Any]:
        """取得完整帳戶資訊"""
        return self._request("GET", "/fapi/v2/account", signed=True)

    # === 持倉管理 ===

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        取得指定交易對的持倉

        Args:
            symbol: 交易對（如 BTCUSDT）

        Returns:
            Position 物件，無持倉時返回 None
        """
        data = self._request("GET", "/fapi/v2/positionRisk", signed=True)

        for pos in data:
            if pos["symbol"] == symbol:
                qty = float(pos["positionAmt"])
                if qty == 0:
                    return None

                return Position(
                    symbol=symbol,
                    side="LONG" if qty > 0 else "SHORT",
                    qty=abs(qty),
                    entry_price=float(pos["entryPrice"]),
                    unrealized_pnl=float(pos["unRealizedProfit"]),
                    leverage=int(pos["leverage"]),
                    margin_type=pos["marginType"].lower(),
                )

        return None

    def get_all_positions(self) -> List[Position]:
        """取得所有持倉"""
        data = self._request("GET", "/fapi/v2/positionRisk", signed=True)
        positions = []

        for pos in data:
            qty = float(pos["positionAmt"])
            if qty != 0:
                positions.append(
                    Position(
                        symbol=pos["symbol"],
                        side="LONG" if qty > 0 else "SHORT",
                        qty=abs(qty),
                        entry_price=float(pos["entryPrice"]),
                        unrealized_pnl=float(pos["unRealizedProfit"]),
                        leverage=int(pos["leverage"]),
                        margin_type=pos["marginType"].lower(),
                    )
                )

        return positions

    # === 槓桿與保證金設定 ===

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        設定槓桿

        Args:
            symbol: 交易對
            leverage: 槓桿倍數 (1-125)

        Returns:
            是否成功
        """
        try:
            self._request(
                "POST",
                "/fapi/v1/leverage",
                {
                    "symbol": symbol,
                    "leverage": leverage,
                },
                signed=True,
            )
            logger.info(f"{symbol} 槓桿設定為 {leverage}x")
            return True
        except Exception as e:
            logger.error(f"設定槓桿失敗: {e}")
            return False

    def set_margin_type(self, symbol: str, margin_type: Literal["ISOLATED", "CROSSED"]) -> bool:
        """
        設定保證金模式

        Args:
            symbol: 交易對
            margin_type: ISOLATED (逐倉) 或 CROSSED (全倉)

        Returns:
            是否成功
        """
        try:
            self._request(
                "POST",
                "/fapi/v1/marginType",
                {
                    "symbol": symbol,
                    "marginType": margin_type,
                },
                signed=True,
            )
            logger.info(f"{symbol} 保證金模式設定為 {margin_type}")
            return True
        except requests.exceptions.HTTPError as e:
            # 如果已經是該模式，API 會返回錯誤，但不影響
            if "No need to change margin type" in str(e.response.text):
                logger.info(f"{symbol} 已經是 {margin_type} 模式")
                return True
            logger.error(f"設定保證金模式失敗: {e}")
            return False

    # === 下單 ===

    def market_buy(self, symbol: str, qty: float) -> Optional[OrderResult]:
        """
        市價買入（開多/平空）

        Args:
            symbol: 交易對
            qty: 數量

        Returns:
            下單結果
        """
        return self._place_order(symbol, "BUY", "MARKET", qty)

    def market_sell(self, symbol: str, qty: float) -> Optional[OrderResult]:
        """
        市價賣出（開空/平多）

        Args:
            symbol: 交易對
            qty: 數量

        Returns:
            下單結果
        """
        return self._place_order(symbol, "SELL", "MARKET", qty)

    def _place_order(
        self,
        symbol: str,
        side: Literal["BUY", "SELL"],
        order_type: str,
        qty: float,
        price: Optional[float] = None,
    ) -> Optional[OrderResult]:
        """
        下單（內部方法）

        Args:
            symbol: 交易對
            side: 方向
            order_type: 訂單類型
            qty: 數量
            price: 限價（僅限價單需要）

        Returns:
            下單結果
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": qty,
        }

        if price and order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = "GTC"

        try:
            data = self._request("POST", "/fapi/v1/order", params, signed=True)

            # 計算平均成交價格
            # 優先從 avgPrice 取得，如果為 0 則從 fills 計算
            avg_price = float(data.get("avgPrice", 0))
            if avg_price == 0 and "fills" in data and len(data["fills"]) > 0:
                # 從成交明細計算加權平均價格
                total_qty = 0
                total_value = 0
                for fill in data["fills"]:
                    fill_qty = float(fill["qty"])
                    fill_price = float(fill["price"])
                    total_qty += fill_qty
                    total_value += fill_qty * fill_price
                if total_qty > 0:
                    avg_price = total_value / total_qty

            result = OrderResult(
                order_id=data["orderId"],
                symbol=data["symbol"],
                side=data["side"],
                type=data["type"],
                qty=float(data["origQty"]),
                price=float(data.get("price", 0)),
                status=data["status"],
                executed_qty=float(data["executedQty"]),
                avg_price=avg_price,
            )

            logger.info(f"下單成功: {side} {qty} {symbol} @ {result.avg_price}")
            return result

        except Exception as e:
            logger.error(f"下單失敗: {e}")
            return None

    def close_position(self, symbol: str) -> Optional[OrderResult]:
        """
        平倉（全部）

        Args:
            symbol: 交易對

        Returns:
            下單結果
        """
        position = self.get_position(symbol)
        if not position:
            logger.info(f"{symbol} 無持倉")
            return None

        # 平倉方向與持倉相反
        if position.side == "LONG":
            return self.market_sell(symbol, position.qty)
        else:
            return self.market_buy(symbol, position.qty)

    # === K 線數據 ===

    def get_klines(
        self,
        symbol: str,
        interval: str = "4h",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        取得 K 線數據

        Args:
            symbol: 交易對
            interval: 時間週期 (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            limit: 數量 (最多 1500)

        Returns:
            K 線列表 [{'timestamp', 'open', 'high', 'low', 'close', 'volume'}, ...]
        """
        data = self._request(
            "GET",
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
        )

        klines = []
        for k in data:
            klines.append(
                {
                    "timestamp": k[0],  # 開盤時間 (毫秒)
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": k[6],  # 收盤時間 (毫秒)
                }
            )

        return klines

    def get_current_price(self, symbol: str) -> float:
        """取得當前價格"""
        data = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(data["price"])

    # === 交易對資訊 ===

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """取得交易所資訊"""
        data = self._request("GET", "/fapi/v1/exchangeInfo")

        if symbol:
            for s in data["symbols"]:
                if s["symbol"] == symbol:
                    return s
            return {}

        return data

    def get_symbol_precision(self, symbol: str) -> Dict[str, int]:
        """
        取得交易對精度設定

        Returns:
            {'price': 價格精度, 'qty': 數量精度}
        """
        info = self.get_exchange_info(symbol)
        if not info:
            return {"price": 2, "qty": 3}

        price_precision = info.get("pricePrecision", 2)
        qty_precision = info.get("quantityPrecision", 3)

        return {"price": price_precision, "qty": qty_precision}

    # === 連線測試 ===

    def test_connection(self) -> bool:
        """測試 API 連線"""
        try:
            self._request("GET", "/fapi/v1/ping")
            logger.info("API 連線成功")
            return True
        except Exception as e:
            logger.error(f"API 連線失敗: {e}")
            return False

    def get_server_time(self) -> int:
        """取得伺服器時間 (毫秒)"""
        data = self._request("GET", "/fapi/v1/time")
        return data["serverTime"]


# === 便利函數 ===


def create_broker_from_env(testnet: bool = False) -> BinanceFuturesBroker:
    """從環境變數創建 Broker"""
    from dotenv import load_dotenv

    load_dotenv()

    return BinanceFuturesBroker(testnet=testnet)


if __name__ == "__main__":
    # 測試連線
    from dotenv import load_dotenv

    load_dotenv()

    broker = BinanceFuturesBroker()

    print("測試 API 連線...")
    if broker.test_connection():
        print("連線成功!")

        print("\n取得帳戶餘額...")
        balance = broker.get_account_balance()
        print(f"  總餘額: {balance['total']:.2f} USDT")
        print(f"  可用餘額: {balance['available']:.2f} USDT")

        print("\n取得 BTC 當前價格...")
        price = broker.get_current_price("BTCUSDT")
        print(f"  BTCUSDT: ${price:,.2f}")

        print("\n取得持倉...")
        positions = broker.get_all_positions()
        if positions:
            for pos in positions:
                print(f"  {pos.symbol}: {pos.side} {pos.qty} @ {pos.entry_price}")
        else:
            print("  無持倉")
    else:
        print("連線失敗!")
