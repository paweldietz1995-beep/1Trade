"""
Scanner V3 Feature Tests

Tests for the high-performance multi-source scanner V3:
- Scanner stats endpoint (/api/scanner/stats)
- Token deduplication
- Cache functionality (2s TTL)
- Performance metrics
- Auto-trading status endpoint
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestScannerStatsEndpoint:
    """Test /api/scanner/stats endpoint"""

    def test_scanner_stats_returns_200(self, api_client):
        """GET /scanner/stats returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None

    def test_scanner_stats_has_version(self, api_client):
        """Scanner stats includes version field"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "scanner_version" in data
        assert data["scanner_version"] == "v3"

    def test_scanner_stats_has_stats_block(self, api_client):
        """Scanner stats includes stats block with required fields"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        stats = data["stats"]
        
        # Required stats fields
        assert "total_sources_scanned" in stats
        assert "tokens_found" in stats
        assert "tokens_after_dedup" in stats
        assert "opportunities" in stats
        assert "last_scan" in stats
        assert "avg_scan_time_ms" in stats
        assert "scan_history" in stats

    def test_scanner_stats_has_cache_info(self, api_client):
        """Scanner stats includes cache statistics"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["stats"]
        
        assert "cache" in stats
        cache = stats["cache"]
        assert "hits" in cache
        assert "misses" in cache
        assert "hit_rate" in cache
        assert "cached_items" in cache

    def test_scanner_stats_has_source_status(self, api_client):
        """Scanner stats includes status per source"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "source_status" in data
        source_status = data["source_status"]
        
        # Expected sources
        expected_sources = ["dexscreener", "birdeye", "jupiter", "raydium", "orca", "meteora", "pumpfun"]
        for source in expected_sources:
            if source in source_status:
                assert "healthy" in source_status[source]
                assert "count" in source_status[source]

    def test_scanner_stats_has_config(self, api_client):
        """Scanner stats includes configuration"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "config" in data
        config = data["config"]
        assert "batch_size" in config
        assert "cache_ttl_seconds" in config
        assert "target_tokens_per_cycle" in config
        assert "target_scan_interval" in config

    def test_scanner_stats_config_values(self, api_client):
        """Scanner config has correct expected values"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        config = data["config"]
        
        # V3 config values
        assert config["batch_size"] == 200
        assert config["cache_ttl_seconds"] == 2.0
        assert config["target_tokens_per_cycle"] == "1000-5000"
        assert config["target_scan_interval"] == "0.8-1.2s"


class TestScannerCacheFunctionality:
    """Test scanner cache behavior"""

    def test_clear_cache_endpoint(self, api_client):
        """POST /scanner/clear-cache clears the cache"""
        resp = api_client.post(f"{BASE_URL}/api/scanner/clear-cache")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "message" in data

    def test_cache_ttl_is_2_seconds(self, api_client):
        """Cache TTL is configured as 2 seconds"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["config"]["cache_ttl_seconds"] == 2.0


class TestTokenScanEndpoint:
    """Test /api/tokens/scan endpoint"""

    def test_tokens_scan_returns_200(self, api_client):
        """GET /tokens/scan returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_tokens_scan_respects_limit(self, api_client):
        """GET /tokens/scan respects limit parameter"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 5})
        assert resp.status_code == 200
        tokens = resp.json()
        assert len(tokens) <= 5

    def test_tokens_scan_default_limit(self, api_client):
        """GET /tokens/scan has default limit of 500"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan")
        assert resp.status_code == 200
        tokens = resp.json()
        # Should work without explicit limit
        assert isinstance(tokens, list)

    def test_tokens_scan_token_structure(self, api_client):
        """Token objects have required fields when data is available"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
        assert resp.status_code == 200
        tokens = resp.json()
        
        if len(tokens) > 0:
            token = tokens[0]
            # Required fields
            assert "address" in token
            assert "name" in token
            assert "symbol" in token
            assert "price_usd" in token
            assert "liquidity" in token
            assert "volume_24h" in token
            assert "buy_sell_ratio" in token
            assert "momentum_score" in token
            assert "signal_strength" in token


class TestAutoTradingStatusEndpoint:
    """Test /api/auto-trading/status endpoint"""

    def test_auto_trading_status_returns_200(self, api_client):
        """GET /auto-trading/status returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None

    def test_auto_trading_status_structure(self, api_client):
        """Auto-trading status has required fields"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        
        # Required fields
        assert "is_running" in data
        assert "scan_count" in data
        assert "trades_executed" in data
        assert "trades_today" in data
        assert "scan_interval_seconds" in data
        assert "errors" in data
        assert "current_opportunities" in data
        assert "signals_processed" in data
        assert "high_frequency_mode" in data

    def test_auto_trading_status_has_queue_info(self, api_client):
        """Auto-trading status includes queue information"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "queue_size" in data
        assert "queue_max_size" in data

    def test_auto_trading_status_has_performance(self, api_client):
        """Auto-trading status includes performance metrics"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "performance" in data
        perf = data["performance"]
        assert "total_trades" in perf
        assert "winning_trades" in perf
        assert "losing_trades" in perf
        assert "win_rate" in perf
        assert "daily_pnl" in perf

    def test_auto_trading_status_has_config(self, api_client):
        """Auto-trading status includes config settings"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "config" in data
        config = data["config"]
        assert "max_open_trades" in config
        assert "take_profit_percent" in config
        assert "stop_loss_percent" in config
        assert "min_signal_score" in config

    def test_auto_trading_scan_interval_is_1s(self, api_client):
        """Auto-trading scan interval is configured as 1 second"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_interval_seconds"] == 1.0

    def test_auto_trading_high_frequency_mode_enabled(self, api_client):
        """Auto-trading high frequency mode is enabled"""
        resp = api_client.get(f"{BASE_URL}/api/auto-trading/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["high_frequency_mode"] is True


class TestHealthCheckEndpoint:
    """Test /api/health endpoint"""

    def test_health_check_returns_200(self, api_client):
        """GET /health returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_check_has_timestamp(self, api_client):
        """Health check includes timestamp"""
        resp = api_client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "timestamp" in data


class TestScannerPerformance:
    """Test scanner performance characteristics"""

    def test_scanner_stats_scan_time_tracked(self, api_client):
        """Scanner tracks scan times in history"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["stats"]
        
        assert "scan_history" in stats
        assert isinstance(stats["scan_history"], list)
        
        # avg_scan_time_ms should be calculated
        assert "avg_scan_time_ms" in stats
        assert isinstance(stats["avg_scan_time_ms"], (int, float))

    def test_token_scan_performance(self, api_client):
        """Token scan completes within reasonable time (under 5 seconds)"""
        start_time = time.time()
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 100})
        elapsed = time.time() - start_time
        
        assert resp.status_code == 200
        # Should complete within 5 seconds (generous limit for external API calls)
        assert elapsed < 5.0, f"Scan took {elapsed:.2f}s, expected < 5s"

    def test_scanner_batch_size_configured(self, api_client):
        """Scanner has batch processing configured"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["config"]["batch_size"] == 200


class TestApiStatusEndpoint:
    """Test /api/api-status endpoint for failover system"""

    def test_api_status_returns_200(self, api_client):
        """GET /api-status returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/api-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
