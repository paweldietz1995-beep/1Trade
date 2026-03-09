"""
Backend tests for wallet sync endpoints.
Tests the new /api/wallet/status, /api/wallet/sync, and /api/wallet/can-trade endpoints.
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestWalletStatusEndpoint:
    """Tests for GET /api/wallet/status endpoint"""
    
    def test_wallet_status_returns_correct_structure(self, api_client):
        """Test that /wallet/status returns expected fields"""
        response = api_client.get(f"{BASE_URL}/api/wallet/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields are present
        required_fields = [
            "wallet_synced",
            "wallet_address",
            "balance_sol",
            "sync_status",
            "last_update",
            "trading_engine_ready",
            "can_trade"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["wallet_synced"], bool)
        assert isinstance(data["balance_sol"], (int, float))
        assert isinstance(data["trading_engine_ready"], bool)
        assert isinstance(data["can_trade"], bool)
        assert data["sync_status"] in ["synced", "syncing", "disconnected", "error"]
    
    def test_wallet_status_balance_non_negative(self, api_client):
        """Test that balance is never negative"""
        response = api_client.get(f"{BASE_URL}/api/wallet/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["balance_sol"] >= 0, "Balance should never be negative"
    
    def test_wallet_status_sync_state_consistency(self, api_client):
        """Test that can_trade matches synced state"""
        response = api_client.get(f"{BASE_URL}/api/wallet/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # can_trade should only be true if wallet is synced AND engine ready
        if data["can_trade"]:
            assert data["wallet_synced"] is True, "can_trade=true requires wallet_synced=true"
            assert data["trading_engine_ready"] is True, "can_trade=true requires trading_engine_ready=true"


class TestWalletCanTradeEndpoint:
    """Tests for GET /api/wallet/can-trade endpoint"""
    
    def test_can_trade_returns_correct_structure(self, api_client):
        """Test that /wallet/can-trade returns expected fields"""
        response = api_client.get(f"{BASE_URL}/api/wallet/can-trade")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        required_fields = [
            "can_start",
            "reason",
            "wallet_synced",
            "trading_engine_ready",
            "initialization_complete"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["can_start"], bool)
        assert isinstance(data["reason"], str)
        assert isinstance(data["wallet_synced"], bool)
        assert isinstance(data["trading_engine_ready"], bool)
        assert isinstance(data["initialization_complete"], bool)
    
    def test_can_trade_reason_explains_state(self, api_client):
        """Test that reason field provides meaningful message"""
        response = api_client.get(f"{BASE_URL}/api/wallet/can-trade")
        
        assert response.status_code == 200
        data = response.json()
        
        # Reason should not be empty
        assert len(data["reason"]) > 0, "Reason should provide explanation"
        
        # If can_start is true, reason should be positive
        if data["can_start"]:
            assert "Ready" in data["reason"] or "ready" in data["reason"].lower(), \
                "When can_start=true, reason should indicate readiness"


class TestWalletSyncEndpoint:
    """Tests for POST /api/wallet/sync endpoint"""
    
    TEST_WALLET_ADDRESS = "DfCAYgk3FZQZWD3tpqAGgNjH5vxWHCqZfREqbqPGvGz8"
    
    def test_wallet_sync_valid_address(self, api_client):
        """Test syncing a valid Solana address"""
        response = api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify success
        assert data["success"] is True
        assert "balance" in data
        assert isinstance(data["balance"], (int, float))
        assert data["balance"] >= 0
    
    def test_wallet_sync_returns_correct_fields(self, api_client):
        """Test that sync returns all expected fields"""
        response = api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["success"]:
            # Verify fields for successful sync
            assert "address" in data
            assert "balance" in data
            assert "status" in data
            assert data["address"] == self.TEST_WALLET_ADDRESS
            assert data["status"] == "synced"
    
    def test_wallet_sync_no_address_fails(self, api_client):
        """Test that sync fails without address"""
        response = api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={}
        )
        
        # FastAPI returns 422 with 'detail' for missing required params
        # Or returns success=false for invalid params
        data = response.json()
        assert response.status_code == 422 or data.get("success") is False or "detail" in data
    
    def test_wallet_sync_updates_status(self, api_client):
        """Test that sync updates the wallet status endpoint"""
        # First sync the wallet
        sync_response = api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS}
        )
        assert sync_response.status_code == 200
        
        # Then verify status is updated
        status_response = api_client.get(f"{BASE_URL}/api/wallet/status")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        
        # If sync succeeded, wallet should be synced
        if sync_response.json().get("success"):
            assert status_data["wallet_synced"] is True
            assert status_data["wallet_address"] == self.TEST_WALLET_ADDRESS
    
    def test_wallet_sync_force_parameter(self, api_client):
        """Test that force parameter triggers resync"""
        # First sync
        api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS}
        )
        
        # Force resync
        response = api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS, "force": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestWalletDisconnect:
    """Tests for POST /api/wallet/disconnect endpoint"""
    
    TEST_WALLET_ADDRESS = "DfCAYgk3FZQZWD3tpqAGgNjH5vxWHCqZfREqbqPGvGz8"
    
    def test_wallet_disconnect_clears_state(self, api_client):
        """Test that disconnect clears wallet state"""
        # First sync to set state
        api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS}
        )
        
        # Disconnect
        response = api_client.post(f"{BASE_URL}/api/wallet/disconnect")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify state is cleared
        status_response = api_client.get(f"{BASE_URL}/api/wallet/status")
        status_data = status_response.json()
        
        assert status_data["wallet_synced"] is False or status_data["wallet_address"] is None
    
    def test_wallet_disconnect_updates_sync_status(self, api_client):
        """Test that disconnect changes sync status to disconnected"""
        response = api_client.post(f"{BASE_URL}/api/wallet/disconnect")
        
        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"


class TestWalletIntegrationFlow:
    """Integration tests for the full wallet sync flow"""
    
    TEST_WALLET_ADDRESS = "DfCAYgk3FZQZWD3tpqAGgNjH5vxWHCqZfREqbqPGvGz8"
    
    def test_full_wallet_lifecycle(self, api_client):
        """Test complete wallet connect -> check status -> disconnect flow"""
        # Step 1: Start disconnected
        api_client.post(f"{BASE_URL}/api/wallet/disconnect")
        
        # Step 2: Verify initial disconnected state
        status = api_client.get(f"{BASE_URL}/api/wallet/status").json()
        # After disconnect, wallet should not be synced
        assert status["wallet_synced"] is False or status["wallet_address"] is None
        
        # Step 3: Sync wallet
        sync_response = api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS}
        )
        assert sync_response.status_code == 200
        
        # Step 4: Verify synced state
        status = api_client.get(f"{BASE_URL}/api/wallet/status").json()
        if sync_response.json().get("success"):
            assert status["wallet_synced"] is True
            assert status["wallet_address"] == self.TEST_WALLET_ADDRESS
        
        # Step 5: Check can-trade
        can_trade = api_client.get(f"{BASE_URL}/api/wallet/can-trade").json()
        if status["wallet_synced"]:
            assert "reason" in can_trade
        
        # Step 6: Disconnect
        disconnect_response = api_client.post(f"{BASE_URL}/api/wallet/disconnect")
        assert disconnect_response.status_code == 200
        
        # Step 7: Verify disconnected
        final_status = api_client.get(f"{BASE_URL}/api/wallet/status").json()
        assert final_status["wallet_synced"] is False or final_status["wallet_address"] is None
    
    def test_wallet_sync_consistency_with_can_trade(self, api_client):
        """Test that wallet/status and wallet/can-trade are consistent"""
        # Sync first
        api_client.post(
            f"{BASE_URL}/api/wallet/sync",
            params={"address": self.TEST_WALLET_ADDRESS}
        )
        
        # Get both endpoints
        status = api_client.get(f"{BASE_URL}/api/wallet/status").json()
        can_trade = api_client.get(f"{BASE_URL}/api/wallet/can-trade").json()
        
        # Both should agree on wallet_synced
        assert status["wallet_synced"] == can_trade["wallet_synced"], \
            "wallet_synced should be consistent between endpoints"
        
        # Both should agree on trading_engine_ready
        assert status["trading_engine_ready"] == can_trade["trading_engine_ready"], \
            "trading_engine_ready should be consistent between endpoints"
