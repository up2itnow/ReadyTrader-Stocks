from app.core.config import settings
from common.idempotency import IdempotencyStore
from common.rate_limiter import FixedWindowRateLimiter
from core.backtest import BacktestEngine
from core.paper import PaperTradingEngine
from core.policy import PolicyEngine
from core.risk import RiskGuardian
from execution.alpaca_service import AlpacaBrokerage
from execution.ibkr_service import IBKRBrokerage
from execution.retail_services import EtradeBrokerage, RobinhoodBrokerage, SchwabBrokerage
from execution.store import ExecutionStore
from execution.tradier_service import TradierBrokerage
from intelligence.insights import InsightStore
from intelligence.learning import Learner
from intelligence.regime import RegimeDetector
from marketdata import (
    IngestMarketDataProvider,
    InMemoryMarketDataStore,
    MarketDataBus,
    StockMarketDataProvider,
    WsStreamManager,
    load_marketdata_plugins,
)
from marketdata.exchange_provider import ExchangeProvider
from observability import AuditLog, Metrics
from strategy.marketplace import StrategyRegistry


class Container:
    def __init__(self):
        # Observability
        self.metrics = Metrics()
        self.audit_log = AuditLog()
        
        # Core Engines
        self.paper_engine = PaperTradingEngine() if settings.PAPER_MODE else None
        self.backtest_engine = BacktestEngine()
        self.regime_detector = RegimeDetector()
        self.risk_guardian = RiskGuardian()
        self.policy_engine = PolicyEngine()
        self.rate_limiter = FixedWindowRateLimiter()
        
        # Stores
        self.execution_store = ExecutionStore()
        self.idempotency_store = IdempotencyStore()
        self.insight_store = InsightStore()
        self.strategy_registry = StrategyRegistry()
        
        # Market Data & Execution
        self.exchange_provider = ExchangeProvider()
        self.marketdata_store = InMemoryMarketDataStore()
        self.marketdata_ws_store = InMemoryMarketDataStore()
        self.ws_manager = WsStreamManager(store=self.marketdata_ws_store, metrics=self.metrics)
        
        self.marketdata_bus = MarketDataBus([
            IngestMarketDataProvider(store=self.marketdata_store),
            IngestMarketDataProvider(store=self.marketdata_ws_store, provider_id="exchange_ws"),
            *load_marketdata_plugins(),
            StockMarketDataProvider(exchange_provider=self.exchange_provider),
        ])
        
        # Brokerages
        self.alpaca_brokerage = AlpacaBrokerage()
        self.tradier_brokerage = TradierBrokerage()
        self.ibkr_brokerage = IBKRBrokerage()
        self.schwab_brokerage = SchwabBrokerage()
        self.etrade_brokerage = EtradeBrokerage()
        self.robinhood_brokerage = RobinhoodBrokerage()
        
        # Mapping for easy lookup
        self.brokerages = {
            "alpaca": self.alpaca_brokerage,
            "tradier": self.tradier_brokerage,
            "ibkr": self.ibkr_brokerage,
            "schwab": self.schwab_brokerage,
            "etrade": self.etrade_brokerage,
            "robinhood": self.robinhood_brokerage
        }
        
        self.learner = Learner(db_path=self.paper_engine.db_path) if settings.PAPER_MODE and self.paper_engine else None

global_container = Container()
