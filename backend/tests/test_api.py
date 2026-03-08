import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


VALID_PIN = "1234"  # PIN set during initial app setup


class TestAuth:
    """Test PIN-based authentication"""

    def test_health_check(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_login_returns_success_and_token(self, api_client):
        """Login with correct PIN returns success and a token"""
        resp = api_client.post(f"{BASE_URL}/api/auth/login", json={"pin": VALID_PIN})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "token" in data
        assert data["token"] is not None and len(data["token"]) > 0

    def test_login_response_has_message(self, api_client):
        """Login response always contains a message field"""
        resp = api_client.post(f"{BASE_URL}/api/auth/login", json={"pin": VALID_PIN})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    def test_login_invalid_pin(self, api_client):
        """Login with wrong PIN returns failure"""
        resp = api_client.post(f"{BASE_URL}/api/auth/login", json={"pin": "00000"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Invalid PIN" in data["message"]

    def test_verify_valid_token(self, api_client):
        """Valid token verification returns true"""
        # Get a token first
        resp = api_client.post(f"{BASE_URL}/api/auth/login", json={"pin": VALID_PIN})
        token = resp.json().get("token")
        assert token is not None, "Login must succeed to test verify"
        
        verify_resp = api_client.post(f"{BASE_URL}/api/auth/verify", params={"token": token})
        assert verify_resp.status_code == 200
        assert verify_resp.json()["valid"] is True

    def test_verify_invalid_token(self, api_client):
        """Invalid token verification returns false"""
        resp = api_client.post(f"{BASE_URL}/api/auth/verify", params={"token": "invalid-token-abc"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


class TestSettings:
    """Test settings endpoints"""

    def test_get_settings(self, api_client):
        """GET /bot/settings returns trading settings"""
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_budget_sol" in data
        assert "max_trade_percent" in data
        assert "take_profit_percent" in data
        assert "stop_loss_percent" in data
        assert "paper_mode" in data
        assert "auto_trade_enabled" in data

    def test_get_settings_new_safety_fields(self, api_client):
        """GET /bot/settings includes new trading safety fields"""
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        assert resp.status_code == 200
        data = resp.json()
        # New safety features
        assert "max_trade_amount_sol" in data
        assert "max_daily_loss_percent" in data
        assert "max_daily_loss_sol" in data
        assert "max_loss_streak" in data
        assert "slippage_bps" in data
        # Validate types
        assert isinstance(data["max_trade_amount_sol"], (int, float))
        assert isinstance(data["max_loss_streak"], int)
        assert isinstance(data["slippage_bps"], int)

    def test_update_settings(self, api_client):
        """PUT /bot/settings updates settings and persists"""
        # Get current settings first
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        settings = resp.json()
        
        # Update budget
        original_budget = settings["total_budget_sol"]
        settings["total_budget_sol"] = 1.0
        settings["paper_mode"] = True
        
        update_resp = api_client.put(f"{BASE_URL}/api/bot/settings", json=settings)
        assert update_resp.status_code == 200
        
        # Verify persistence
        get_resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        updated = get_resp.json()
        assert updated["total_budget_sol"] == 1.0
        
        # Restore original
        settings["total_budget_sol"] = original_budget
        api_client.put(f"{BASE_URL}/api/bot/settings", json=settings)


class TestTokenScanner:
    """Test token scanning endpoints"""

    def test_scan_tokens(self, api_client):
        """GET /tokens/scan returns token list"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_scan_tokens_fields(self, api_client):
        """Token objects have required fields"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 3})
        assert resp.status_code == 200
        tokens = resp.json()
        if len(tokens) > 0:
            token = tokens[0]
            assert "address" in token
            assert "name" in token
            assert "symbol" in token
            assert "price_usd" in token
            assert "price_change_24h" in token
            assert "liquidity" in token
            assert "risk_analysis" in token

    def test_sol_price_endpoint(self, api_client):
        """GET /market/sol-price returns price"""
        resp = api_client.get(f"{BASE_URL}/api/market/sol-price")
        assert resp.status_code == 200
        data = resp.json()
        assert "price" in data
        assert isinstance(data["price"], (int, float))
        assert data["price"] > 0


class TestTrades:
    """Test trade creation and retrieval"""

    def test_create_paper_trade(self, api_client):
        """POST /trades creates a paper trade"""
        trade_data = {
            "token_address": "TEST_ADDR_" + str(int(time.time())),
            "token_symbol": "TTEST",
            "token_name": "Test Token",
            "trade_type": "BUY",
            "amount_sol": 0.1,
            "price_entry": 0.0001,
            "take_profit_percent": 100.0,
            "stop_loss_percent": 30.0,
            "paper_trade": True,
            "wallet_address": None
        }
        resp = api_client.post(f"{BASE_URL}/api/trades", json=trade_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OPEN"
        assert data["paper_trade"] is True
        assert data["trade_type"] == "BUY"
        assert "id" in data

    def test_trade_has_tx_signature_field(self, api_client):
        """Trade object includes tx_signature field for Solscan links"""
        trade_data = {
            "token_address": "TX_SIG_TEST_" + str(int(time.time())),
            "token_symbol": "TXTEST",
            "token_name": "TX Test Token",
            "trade_type": "BUY",
            "amount_sol": 0.05,
            "price_entry": 0.0001,
            "take_profit_percent": 100.0,
            "stop_loss_percent": 30.0,
            "paper_trade": True,
            "tx_signature": "5XrZwT1234567890abcdef"  # Mock tx signature
        }
        resp = api_client.post(f"{BASE_URL}/api/trades", json=trade_data)
        assert resp.status_code == 200
        data = resp.json()
        assert "tx_signature" in data
        assert data["tx_signature"] == "5XrZwT1234567890abcdef"

    def test_get_trades(self, api_client):
        """GET /trades returns list of trades"""
        resp = api_client.get(f"{BASE_URL}/api/trades")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_trades_by_status(self, api_client):
        """GET /trades?status=OPEN filters by status"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "OPEN"})
        assert resp.status_code == 200
        trades = resp.json()
        for trade in trades:
            assert trade["status"] == "OPEN"

    def test_close_trade(self, api_client):
        """PUT /trades/{id}/close closes a trade"""
        # Create a trade first
        trade_data = {
            "token_address": "CLOSE_TEST_" + str(int(time.time())),
            "token_symbol": "CTEST",
            "token_name": "Close Test",
            "trade_type": "BUY",
            "amount_sol": 0.05,
            "price_entry": 0.0001,
            "take_profit_percent": 100.0,
            "stop_loss_percent": 30.0,
            "paper_trade": True
        }
        create_resp = api_client.post(f"{BASE_URL}/api/trades", json=trade_data)
        trade_id = create_resp.json()["id"]
        
        # Close the trade
        close_resp = api_client.put(
            f"{BASE_URL}/api/trades/{trade_id}/close",
            params={"exit_price": 0.00012}
        )
        assert close_resp.status_code == 200
        data = close_resp.json()
        assert data["success"] is True


class TestPortfolio:
    """Test portfolio endpoint"""

    def test_get_portfolio(self, api_client):
        """GET /portfolio returns portfolio summary"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_budget_sol" in data
        assert "available_sol" in data
        assert "in_trades_sol" in data
        assert "total_pnl" in data
        assert "open_trades" in data
        assert "closed_trades" in data
        assert "win_rate" in data

    def test_portfolio_has_safety_status_fields(self, api_client):
        """Portfolio includes loss streak and pause status for safety features"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        # Safety-related fields
        assert "daily_pnl" in data
        assert "loss_streak" in data
        assert "is_paused" in data
        # Validate types
        assert isinstance(data["loss_streak"], int)
        assert isinstance(data["is_paused"], bool)


class TestTradingOpportunities:
    """Test trading opportunities endpoint"""

    def test_get_opportunities(self, api_client):
        """GET /opportunities returns list of trading opportunities"""
        resp = api_client.get(f"{BASE_URL}/api/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_opportunities_structure(self, api_client):
        """Trading opportunities have expected structure"""
        resp = api_client.get(f"{BASE_URL}/api/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        if len(data) > 0:
            opp = data[0]
            assert "token" in opp
            assert "suggested_action" in opp
            assert "confidence" in opp
            assert "risk_level" in opp



class TestAutoTrading:
    """Test auto trading engine endpoints"""

    def test_auto_trading_status_initial(self, api_client):
        """GET /auto-trading/status returns status structure"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_running" in data
        assert "scan_count" in data
        assert "trades_executed" in data
        assert "scan_interval_seconds" in data
        assert isinstance(data["is_running"], bool)
        assert isinstance(data["scan_count"], int)
        assert isinstance(data["scan_interval_seconds"], int)

    def test_auto_trading_start(self, api_client):
        """POST /auto-trading/start starts the engine"""
        # First ensure it's stopped
        api_client.post(f"{BASE_URL}/api/auto-trading/stop")
        
        resp = api_client.post(f"{BASE_URL}/api/auto-trading/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "interval" in data
        assert data["interval"] == 3
        
        # Check status is running
        status_resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert status_resp.json()["is_running"] is True
        
        # Cleanup: stop it
        api_client.post(f"{BASE_URL}/api/auto-trading/stop")

    def test_auto_trading_stop(self, api_client):
        """POST /auto-trading/stop stops the engine and returns stats"""
        # Start first
        api_client.post(f"{BASE_URL}/api/auto-trading/start")
        time.sleep(0.5)  # Let it run briefly
        
        resp = api_client.post(f"{BASE_URL}/api/auto-trading/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "stats" in data
        assert "scan_count" in data["stats"]
        assert "trades_executed" in data["stats"]
        
        # Verify stopped
        status_resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert status_resp.json()["is_running"] is False

    def test_auto_trading_opportunities_endpoint(self, api_client):
        """GET /auto-trading/opportunities returns list"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_auto_trading_status_has_scan_interval_3_seconds(self, api_client):
        """Auto trading engine uses 3-second scan interval"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_interval_seconds"] == 3


class TestMomentumThresholds:
    """Test new momentum detection thresholds in bot settings"""

    def test_settings_has_momentum_thresholds(self, api_client):
        """Bot settings include new momentum threshold fields"""
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        assert resp.status_code == 200
        data = resp.json()
        # New momentum threshold fields
        assert "min_momentum_score" in data
        assert "min_volume_surge_percent" in data
        assert "min_buyers_5m" in data

    def test_momentum_thresholds_values(self, api_client):
        """Momentum thresholds have expected default values"""
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_momentum_score"] == 70
        assert data["min_volume_surge_percent"] == 150.0
        assert data["min_buyers_5m"] == 30


class TestTokenFilters:
    """Test stricter token filters"""

    def test_min_liquidity_filter(self, api_client):
        """Minimum liquidity filter is set to $5000"""
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_liquidity_usd"] >= 5000.0

    def test_min_volume_filter(self, api_client):
        """Minimum volume filter is set to $10000"""
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_volume_usd"] >= 10000.0

    def test_scan_interval_is_3_seconds(self, api_client):
        """Scan interval is set to 3 seconds"""
        resp = api_client.get(f"{BASE_URL}/api/bot/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_interval_seconds"] == 3


class TestSystemHealth:
    """Test system health diagnostics endpoint"""

    def test_system_health_endpoint_exists(self, api_client):
        """GET /system/health returns 200"""
        resp = api_client.get(f"{BASE_URL}/api/system/health")
        assert resp.status_code == 200

    def test_system_health_has_all_components(self, api_client):
        """System health returns all component statuses"""
        resp = api_client.get(f"{BASE_URL}/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        # All required status fields
        assert "wallet_ok" in data
        assert "rpc_ok" in data
        assert "scanner_ok" in data
        assert "trading_engine_ok" in data
        assert "database_ok" in data
        assert "overall_ok" in data
        assert "details" in data
        assert "timestamp" in data

    def test_system_health_component_types(self, api_client):
        """System health components have correct types"""
        resp = api_client.get(f"{BASE_URL}/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["wallet_ok"], bool)
        assert isinstance(data["rpc_ok"], bool)
        assert isinstance(data["scanner_ok"], bool)
        assert isinstance(data["trading_engine_ok"], bool)
        assert isinstance(data["database_ok"], bool)
        assert isinstance(data["overall_ok"], bool)
        assert isinstance(data["details"], dict)

    def test_system_health_database_connected(self, api_client):
        """Database should be connected"""
        resp = api_client.get(f"{BASE_URL}/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database_ok"] is True
        assert "database" in data["details"]

    def test_system_health_rpc_connected(self, api_client):
        """RPC should be connected (at least one endpoint)"""
        resp = api_client.get(f"{BASE_URL}/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rpc_ok"] is True
        assert "rpc" in data["details"]
        # RPC details should have latency info
        if isinstance(data["details"]["rpc"], dict):
            assert "latency_ms" in data["details"]["rpc"]

    def test_system_health_trading_engine_ok(self, api_client):
        """Trading engine should always be OK if API is running"""
        resp = api_client.get(f"{BASE_URL}/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trading_engine_ok"] is True
        assert "trading_engine" in data["details"]


class TestWalletBalance:
    """Test wallet balance endpoint via backend RPC"""

    def test_wallet_balance_endpoint_exists(self, api_client):
        """GET /wallet/balance returns 200"""
        resp = api_client.get(f"{BASE_URL}/api/wallet/balance", params={"address": ""})
        assert resp.status_code == 200

    def test_wallet_balance_no_address(self, api_client):
        """Empty address returns error"""
        resp = api_client.get(f"{BASE_URL}/api/wallet/balance", params={"address": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 0
        assert "error" in data or data.get("success") is False or "No address" in data.get("error", "")

    def test_wallet_balance_with_valid_address(self, api_client):
        """Valid Solana address returns balance structure"""
        # Using a known address (Solana Foundation's address)
        test_address = "GhBtSKy6t1CVLGYt9bQKfjhvKpVpP7H9pWJJFdQ6WhQf"
        resp = api_client.get(f"{BASE_URL}/api/wallet/balance", params={"address": test_address})
        assert resp.status_code == 200
        data = resp.json()
        assert "balance" in data
        assert isinstance(data["balance"], (int, float))
        # If successful, should have success flag or endpoint info
        if data.get("success"):
            assert "endpoint" in data
            assert "lamports" in data

    def test_wallet_balance_response_structure(self, api_client):
        """Wallet balance returns expected structure"""
        # Using SOL mint address as test (it will have 0 balance but valid response)
        test_address = "So11111111111111111111111111111111111111112"
        resp = api_client.get(f"{BASE_URL}/api/wallet/balance", params={"address": test_address})
        assert resp.status_code == 200
        data = resp.json()
        # Should have balance field regardless of success/failure
        assert "balance" in data


class TestLossStreakReset:
    """Test loss streak reset endpoint"""

    def test_reset_loss_streak_endpoint_exists(self, api_client):
        """POST /trading/reset-loss-streak returns 200"""
        resp = api_client.post(f"{BASE_URL}/api/trading/reset-loss-streak")
        assert resp.status_code == 200

    def test_reset_loss_streak_returns_success(self, api_client):
        """Reset returns success flag"""
        resp = api_client.post(f"{BASE_URL}/api/trading/reset-loss-streak")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "message" in data

    def test_reset_loss_streak_has_previous_streak_info(self, api_client):
        """Reset returns previous streak info"""
        resp = api_client.post(f"{BASE_URL}/api/trading/reset-loss-streak")
        assert resp.status_code == 200
        data = resp.json()
        assert "previous_streak" in data
        assert isinstance(data["previous_streak"], int)

    def test_reset_loss_streak_has_note(self, api_client):
        """Reset includes helpful note"""
        resp = api_client.post(f"{BASE_URL}/api/trading/reset-loss-streak")
        assert resp.status_code == 200
        data = resp.json()
        assert "note" in data


class TestCanEnableLive:
    """Test live trading safety check endpoint"""

    def test_can_enable_live_endpoint_exists(self, api_client):
        """GET /trading/can-enable-live returns 200"""
        resp = api_client.get(f"{BASE_URL}/api/trading/can-enable-live")
        assert resp.status_code == 200

    def test_can_enable_live_has_can_enable_flag(self, api_client):
        """Response includes can_enable boolean"""
        resp = api_client.get(f"{BASE_URL}/api/trading/can-enable-live")
        assert resp.status_code == 200
        data = resp.json()
        assert "can_enable" in data
        assert isinstance(data["can_enable"], bool)

    def test_can_enable_live_has_blockers_list(self, api_client):
        """Response includes blockers list"""
        resp = api_client.get(f"{BASE_URL}/api/trading/can-enable-live")
        assert resp.status_code == 200
        data = resp.json()
        assert "blockers" in data
        assert isinstance(data["blockers"], list)

    def test_can_enable_live_has_warnings_list(self, api_client):
        """Response includes warnings list"""
        resp = api_client.get(f"{BASE_URL}/api/trading/can-enable-live")
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert isinstance(data["warnings"], list)

    def test_can_enable_live_has_system_health(self, api_client):
        """Response includes system health summary"""
        resp = api_client.get(f"{BASE_URL}/api/trading/can-enable-live")
        assert resp.status_code == 200
        data = resp.json()
        assert "system_health" in data
        health = data["system_health"]
        assert "rpc" in health
        assert "scanner" in health
        assert "database" in health
        assert "trading_engine" in health

    def test_can_enable_live_has_portfolio_info(self, api_client):
        """Response includes portfolio info"""
        resp = api_client.get(f"{BASE_URL}/api/trading/can-enable-live")
        assert resp.status_code == 200
        data = resp.json()
        assert "portfolio" in data
        portfolio = data["portfolio"]
        assert "available_sol" in portfolio
        assert "loss_streak" in portfolio
        assert "is_paused" in portfolio
