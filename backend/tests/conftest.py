import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(autouse=True)
def cleanup_test_trades(api_client):
    """Clean up any open test trades before and after each test"""
    yield
    # Cleanup after test - close any open trades with TEST_ prefix
    try:
        resp = api_client.get(f"{BASE_URL}/api/trades", params={"status": "OPEN"})
        if resp.status_code == 200:
            trades = resp.json()
            for trade in trades:
                if trade.get("token_address", "").startswith("TEST_") or \
                   trade.get("token_address", "").startswith("TX_SIG_TEST_") or \
                   trade.get("token_address", "").startswith("CLOSE_TEST_"):
                    api_client.put(
                        f"{BASE_URL}/api/trades/{trade['id']}/close",
                        params={"exit_price": trade.get("price_entry", 0.0001)}
                    )
    except Exception:
        pass  # Cleanup failure shouldn't fail tests
