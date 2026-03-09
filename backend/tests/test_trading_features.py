import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

VALID_PIN = "1234"

class TestAutoTradingEngine:
    """Test Auto-Trading Engine functionality"""

    def test_auto_trading_status_endpoint(self, api_client):
        """GET /auto-trading/status returns comprehensive status"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        
        # Core fields
        assert "is_running" in data
        assert "scan_count" in data
        assert "trades_executed" in data
        assert "trades_today" in data
        assert "scan_interval_seconds" in data
        
        # Performance metrics
        assert "performance" in data
        perf = data["performance"]
        assert "total_trades" in perf
        assert "winning_trades" in perf
        assert "losing_trades" in perf
        assert "win_rate" in perf
        assert "daily_pnl" in perf
        assert "max_drawdown" in perf
        
        # Config section
        assert "config" in data
        config = data["config"]
        assert "max_open_trades" in config
        assert "take_profit_percent" in config
        assert "stop_loss_percent" in config
        assert "min_signal_score" in config

    def test_auto_trading_start_returns_config(self, api_client):
        """POST /auto-trading/start returns success and config"""
        # Ensure stopped first
        api_client.post(f"{BASE_URL}/api/auto-trading/stop")
        time.sleep(0.5)
        
        resp = api_client.post(f"{BASE_URL}/api/auto-trading/start")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["success"] is True
        assert "config" in data
        assert "scan_interval_seconds" in data["config"]
        assert "max_open_trades" in data["config"]
        
        # Cleanup - stop
        api_client.post(f"{BASE_URL}/api/auto-trading/stop")

    def test_auto_trading_stop(self, api_client):
        """POST /auto-trading/stop returns session stats"""
        # Start first
        api_client.post(f"{BASE_URL}/api/auto-trading/start")
        time.sleep(1)
        
        resp = api_client.post(f"{BASE_URL}/api/auto-trading/stop")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["success"] is True
        assert "session_stats" in data
        stats = data["session_stats"]
        assert "scan_count" in stats
        assert "trades_executed" in stats
        assert "win_rate" in stats

    def test_auto_trading_reset(self, api_client):
        """POST /auto-trading/reset clears state"""
        resp = api_client.post(f"{BASE_URL}/api/auto-trading/reset")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["success"] is True
        
        # Verify reset
        status_resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        status = status_resp.json()
        assert status["is_running"] is False
        assert status["scan_count"] == 0
        assert status["signals_processed"] == 0


class TestEarlyPumpDetection:
    """Test Early Pump Detection endpoints"""

    def test_get_early_pumps(self, api_client):
        """GET /early-pumps returns detected pump list"""
        resp = api_client.get(f"{BASE_URL}/api/early-pumps")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "detected_pumps" in data
        assert "count" in data
        assert isinstance(data["detected_pumps"], list)
        assert isinstance(data["count"], int)

    def test_scan_early_pumps(self, api_client):
        """POST /scan-early-pumps triggers manual scan"""
        resp = api_client.post(f"{BASE_URL}/api/scan-early-pumps")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "detected" in data
        assert "total_scanned" in data
        assert isinstance(data["detected"], list)
        assert isinstance(data["total_scanned"], int)


class TestSmartWalletTracker:
    """Test Smart Wallet Tracker endpoints"""

    def test_get_smart_wallets(self, api_client):
        """GET /smart-wallets returns tracked wallets"""
        resp = api_client.get(f"{BASE_URL}/api/smart-wallets")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_add_smart_wallet(self, api_client):
        """POST /smart-wallets adds a new wallet"""
        test_address = f"TEST_WALLET_{int(time.time())}"
        resp = api_client.post(
            f"{BASE_URL}/api/smart-wallets",
            params={"address": test_address}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # The endpoint returns a SmartWallet object
        assert "address" in data
        assert data["address"] == test_address
        assert "is_tracking" in data
        assert data["is_tracking"] is True
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/smart-wallets/{test_address}")

    def test_add_duplicate_wallet_fails(self, api_client):
        """Adding same wallet twice returns 400 error"""
        test_address = f"TEST_DUPE_{int(time.time())}"
        
        # Add first time
        api_client.post(
            f"{BASE_URL}/api/smart-wallets",
            params={"address": test_address}
        )
        
        # Add second time - should fail with 400
        resp = api_client.post(
            f"{BASE_URL}/api/smart-wallets",
            params={"address": test_address}
        )
        assert resp.status_code == 400
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/smart-wallets/{test_address}")

    def test_remove_smart_wallet(self, api_client):
        """DELETE /smart-wallets/{address} removes wallet"""
        test_address = f"TEST_REMOVE_{int(time.time())}"
        
        # Add wallet first
        api_client.post(
            f"{BASE_URL}/api/smart-wallets",
            params={"address": test_address}
        )
        
        # Remove it
        resp = api_client.delete(f"{BASE_URL}/api/smart-wallets/{test_address}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_get_copy_signals(self, api_client):
        """GET /smart-wallets/copy-signals returns pending signals"""
        resp = api_client.get(f"{BASE_URL}/api/smart-wallets/copy-signals")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestAPIFailover:
    """Test API Failover system"""

    def test_get_api_status(self, api_client):
        """GET /api-status returns API health"""
        resp = api_client.get(f"{BASE_URL}/api/api-status")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "current_api" in data
        assert "status" in data
        
        # Check status for all APIs
        status = data["status"]
        assert "dexscreener" in status
        assert "birdeye" in status
        assert "jupiter" in status
        
        # Each API should have health info
        for api_name, api_info in status.items():
            assert "healthy" in api_info
            assert "failures" in api_info


class TestCrashRecovery:
    """Test Crash Recovery system"""

    def test_save_bot_state(self, api_client):
        """POST /bot/save-state saves current state"""
        resp = api_client.post(f"{BASE_URL}/api/bot/save-state")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["success"] is True

    def test_get_recovery_state(self, api_client):
        """GET /bot/recover-state returns saved state"""
        # Save state first
        api_client.post(f"{BASE_URL}/api/bot/save-state")
        
        resp = api_client.get(f"{BASE_URL}/api/bot/recover-state")
        assert resp.status_code == 200
        data = resp.json()
        
        # If state exists, should have these fields
        if "type" in data:
            assert data["type"] == "trading_state"
            assert "is_running" in data
            assert "scan_count" in data
            assert "saved_at" in data

    def test_trigger_recovery(self, api_client):
        """POST /bot/recover triggers crash recovery"""
        resp = api_client.post(f"{BASE_URL}/api/bot/recover")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "recovered" in data
        assert "active_trades_restored" in data


class TestActivityFeed:
    """Test Activity Feed endpoints"""

    def test_get_activity_feed(self, api_client):
        """GET /activity returns recent events"""
        resp = api_client.get(f"{BASE_URL}/api/activity", params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        
        assert isinstance(data, list)
        
        if len(data) > 0:
            event = data[0]
            assert "id" in event
            assert "type" in event
            assert "token" in event
            assert "timestamp" in event

    def test_clear_activity_feed(self, api_client):
        """POST /activity/clear clears the feed"""
        resp = api_client.post(f"{BASE_URL}/api/activity/clear")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["success"] is True


class TestSystemModules:
    """Test System Modules status"""

    def test_get_system_modules(self, api_client):
        """GET /system/modules returns all module statuses"""
        resp = api_client.get(f"{BASE_URL}/api/system/modules")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "modules" in data
        assert "engine_config" in data
        
        modules = data["modules"]
        expected_modules = [
            "market_scanner",
            "early_pump_detector", 
            "momentum_analyzer",
            "smart_wallet_tracker",
            "trade_monitor",
            "risk_manager",
            "api_failover",
            "crash_recovery"
        ]
        
        for module in expected_modules:
            assert module in modules, f"Missing module: {module}"
            assert "status" in modules[module]

    def test_engine_config_in_system_modules(self, api_client):
        """Engine config contains all expected settings"""
        resp = api_client.get(f"{BASE_URL}/api/system/modules")
        assert resp.status_code == 200
        config = resp.json()["engine_config"]
        
        required_config = [
            "scan_interval_seconds",
            "max_tokens_per_scan",
            "max_open_trades",
            "take_profit_percent",
            "stop_loss_percent",
            "min_signal_score",
            "daily_loss_limit_percent"
        ]
        
        for key in required_config:
            assert key in config, f"Missing config key: {key}"


class TestPortfolioCalculation:
    """Test Portfolio summary calculation"""

    def test_portfolio_summary(self, api_client):
        """GET /portfolio returns comprehensive summary"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        
        required_fields = [
            "total_budget_sol",
            "available_sol",
            "in_trades_sol",
            "total_pnl",
            "total_pnl_percent",
            "open_trades",
            "closed_trades",
            "win_rate",
            "daily_pnl",
            "loss_streak",
            "is_paused"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_portfolio_win_rate_calculation(self, api_client):
        """Win rate is calculated correctly"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        
        # Win rate should be between 0 and 100
        assert 0 <= data["win_rate"] <= 100


class TestTradeCreationAndClosing:
    """Test trade creation and closing flow"""

    def test_create_trade_returns_all_fields(self, api_client):
        """POST /trades returns complete trade object"""
        trade_data = {
            "token_address": f"TEST_TOKEN_{int(time.time())}",
            "token_symbol": "TEST",
            "token_name": "Test Token",
            "trade_type": "BUY",
            "amount_sol": 0.01,
            "price_entry": 0.0001,
            "take_profit_percent": 50,
            "stop_loss_percent": 25,
            "paper_trade": True,
            "auto_trade": False
        }
        
        resp = api_client.post(f"{BASE_URL}/api/trades", json=trade_data)
        assert resp.status_code == 200
        trade = resp.json()
        
        assert "id" in trade
        assert "token_address" in trade
        assert "token_symbol" in trade
        assert "status" in trade
        assert trade["status"] == "OPEN"
        assert "take_profit" in trade
        assert "stop_loss" in trade
        assert "paper_trade" in trade
        
        # Cleanup
        api_client.post(f"{BASE_URL}/api/trades/{trade['id']}/close", params={"reason": "TEST_CLEANUP"})

    def test_close_trade_returns_pnl(self, api_client):
        """POST /trades/{id}/close returns P&L calculation"""
        # Create trade
        trade_data = {
            "token_address": f"TEST_CLOSE_{int(time.time())}",
            "token_symbol": "CLOSE",
            "token_name": "Close Test",
            "trade_type": "BUY",
            "amount_sol": 0.01,
            "price_entry": 0.0001,
            "take_profit_percent": 50,
            "stop_loss_percent": 25,
            "paper_trade": True
        }
        
        create_resp = api_client.post(f"{BASE_URL}/api/trades", json=trade_data)
        trade_id = create_resp.json()["id"]
        
        # Close trade
        close_resp = api_client.post(
            f"{BASE_URL}/api/trades/{trade_id}/close",
            params={"reason": "MANUAL"}
        )
        assert close_resp.status_code == 200
        close_data = close_resp.json()
        
        assert close_data["success"] is True
        assert "pnl" in close_data
        assert "pnl_percent" in close_data
        assert "exit_price" in close_data


class TestTokenScanner:
    """Test Token Scanner with filtering"""

    def test_scan_tokens_with_limit(self, api_client):
        """GET /tokens/scan respects limit parameter"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 5})
        assert resp.status_code == 200
        tokens = resp.json()
        
        assert isinstance(tokens, list)
        assert len(tokens) <= 5

    def test_scan_tokens_has_risk_analysis(self, api_client):
        """Scanned tokens include risk analysis"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 3})
        assert resp.status_code == 200
        tokens = resp.json()
        
        if len(tokens) > 0:
            token = tokens[0]
            assert "risk_analysis" in token
            
            if token["risk_analysis"]:
                risk = token["risk_analysis"]
                assert "honeypot_risk" in risk
                assert "rugpull_risk" in risk
                assert "risk_score" in risk
