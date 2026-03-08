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
        return data["id"]

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
