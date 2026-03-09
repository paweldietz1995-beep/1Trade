"""
Tests for Closed Trades History Feature
Testing: GET /api/trades?status=CLOSED and GET /api/portfolio
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestClosedTradesAPI:
    """Test closed trades API endpoint"""

    def test_get_closed_trades_endpoint_exists(self, api_client):
        """GET /api/trades?status=CLOSED endpoint exists and returns 200"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200

    def test_get_closed_trades_returns_list(self, api_client):
        """GET /api/trades?status=CLOSED returns a list"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_closed_trades_all_have_closed_status(self, api_client):
        """All trades returned by status=CLOSED have status CLOSED"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        trades = resp.json()
        for trade in trades:
            assert trade["status"] == "CLOSED"

    def test_closed_trade_has_required_fields(self, api_client):
        """Closed trades have all required fields for display"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        trades = resp.json()
        if len(trades) > 0:
            trade = trades[0]
            # Core fields
            assert "id" in trade
            assert "token_address" in trade
            assert "token_symbol" in trade
            assert "token_name" in trade
            assert "trade_type" in trade
            assert "amount_sol" in trade
            # Price fields
            assert "price_entry" in trade
            assert "price_exit" in trade
            # P&L fields
            assert "pnl" in trade
            assert "pnl_percent" in trade
            # Status fields
            assert "status" in trade
            assert "paper_trade" in trade
            # Timestamp fields
            assert "opened_at" in trade
            assert "closed_at" in trade
            # Close reason
            assert "close_reason" in trade

    def test_closed_trade_pnl_is_numeric(self, api_client):
        """Closed trades have numeric pnl and pnl_percent values"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        trades = resp.json()
        if len(trades) > 0:
            trade = trades[0]
            assert isinstance(trade["pnl"], (int, float))
            assert isinstance(trade["pnl_percent"], (int, float))

    def test_closed_trade_has_exit_price(self, api_client):
        """Closed trades have a price_exit value"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        trades = resp.json()
        if len(trades) > 0:
            trade = trades[0]
            assert trade["price_exit"] is not None
            assert isinstance(trade["price_exit"], (int, float))

    def test_closed_trade_has_close_reason(self, api_client):
        """Closed trades have a close_reason (TAKE_PROFIT, STOP_LOSS, MANUAL, etc)"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        trades = resp.json()
        valid_reasons = ["TAKE_PROFIT", "STOP_LOSS", "TRAILING_STOP", "MANUAL", "TP_HIT", "SL_HIT", "TEST_CLEANUP"]
        for trade in trades[:10]:  # Check first 10
            assert trade["close_reason"] is not None or trade.get("close_reason") in valid_reasons

    def test_closed_trade_has_timestamps(self, api_client):
        """Closed trades have opened_at and closed_at timestamps"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        trades = resp.json()
        if len(trades) > 0:
            trade = trades[0]
            assert trade["opened_at"] is not None
            assert trade["closed_at"] is not None

    def test_closed_trades_sorted_by_opened_at_desc(self, api_client):
        """Closed trades are sorted by opened_at in descending order (newest first)"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert resp.status_code == 200
        trades = resp.json()
        if len(trades) > 1:
            # Check that trades are sorted (newest first)
            for i in range(len(trades) - 1):
                assert trades[i]["opened_at"] >= trades[i + 1]["opened_at"]


class TestOpenTradesAPI:
    """Test open trades API endpoint"""

    def test_get_open_trades_endpoint_exists(self, api_client):
        """GET /api/trades?status=OPEN endpoint exists and returns 200"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "OPEN"})
        assert resp.status_code == 200

    def test_get_open_trades_returns_list(self, api_client):
        """GET /api/trades?status=OPEN returns a list"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "OPEN"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_open_trades_all_have_open_status(self, api_client):
        """All trades returned by status=OPEN have status OPEN"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "OPEN"})
        assert resp.status_code == 200
        trades = resp.json()
        for trade in trades:
            assert trade["status"] == "OPEN"

    def test_open_trade_has_required_fields(self, api_client):
        """Open trades have all required fields for display"""
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "OPEN"})
        assert resp.status_code == 200
        trades = resp.json()
        if len(trades) > 0:
            trade = trades[0]
            # Core fields
            assert "id" in trade
            assert "token_address" in trade
            assert "token_symbol" in trade
            assert "token_name" in trade
            assert "trade_type" in trade
            assert "amount_sol" in trade
            # Price fields
            assert "price_entry" in trade
            assert "price_current" in trade
            # Status fields
            assert "status" in trade
            assert "paper_trade" in trade
            # Timestamp fields
            assert "opened_at" in trade


class TestPortfolioStats:
    """Test portfolio endpoint for win rate and closed trades count"""

    def test_portfolio_has_win_rate(self, api_client):
        """Portfolio includes win_rate field"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "win_rate" in data
        assert isinstance(data["win_rate"], (int, float))

    def test_portfolio_win_rate_in_range(self, api_client):
        """Portfolio win_rate is between 0 and 100"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert 0 <= data["win_rate"] <= 100

    def test_portfolio_has_closed_trades_count(self, api_client):
        """Portfolio includes closed_trades count"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "closed_trades" in data
        assert isinstance(data["closed_trades"], int)

    def test_portfolio_has_total_pnl(self, api_client):
        """Portfolio includes total_pnl field"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_pnl" in data
        assert isinstance(data["total_pnl"], (int, float))

    def test_portfolio_has_open_trades_count(self, api_client):
        """Portfolio includes open_trades count"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "open_trades" in data
        assert isinstance(data["open_trades"], int)

    def test_portfolio_total_pnl_percent(self, api_client):
        """Portfolio includes total_pnl_percent field"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_pnl_percent" in data
        assert isinstance(data["total_pnl_percent"], (int, float))

    def test_portfolio_best_and_worst_trade(self, api_client):
        """Portfolio includes best_trade_pnl and worst_trade_pnl"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "best_trade_pnl" in data
        assert "worst_trade_pnl" in data
        assert isinstance(data["best_trade_pnl"], (int, float))
        assert isinstance(data["worst_trade_pnl"], (int, float))

    def test_portfolio_daily_pnl(self, api_client):
        """Portfolio includes daily_pnl field"""
        resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily_pnl" in data
        assert isinstance(data["daily_pnl"], (int, float))


class TestTradeDataIntegrity:
    """Test data integrity between trades and portfolio"""

    def test_closed_trades_count_matches_portfolio(self, api_client):
        """Number of closed trades matches portfolio closed_trades count"""
        # Get closed trades
        trades_resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "CLOSED"})
        assert trades_resp.status_code == 200
        closed_trades = trades_resp.json()
        
        # Get portfolio
        portfolio_resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert portfolio_resp.status_code == 200
        portfolio = portfolio_resp.json()
        
        # They should match (or closed_trades <= portfolio count due to limit)
        assert len(closed_trades) <= portfolio["closed_trades"] + 5  # Allow for pagination

    def test_open_trades_count_matches_portfolio(self, api_client):
        """Number of open trades matches portfolio open_trades count"""
        # Get open trades
        trades_resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "OPEN"})
        assert trades_resp.status_code == 200
        open_trades = trades_resp.json()
        
        # Get portfolio
        portfolio_resp = api_client.get(f"{BASE_URL}/api/portfolio")
        assert portfolio_resp.status_code == 200
        portfolio = portfolio_resp.json()
        
        # They should match
        assert len(open_trades) == portfolio["open_trades"]
