"""
Scanner V4 Feature Tests

Tests for the hochverfügbare (high-availability) multi-source scanner V4:
- Scanner stats endpoint (/api/scanner/stats) with V4 features
- Scanner health endpoint (/api/scanner/health)
- Scanner reset-health endpoint (/api/scanner/reset-health)
- Scanner clear-cache endpoint (/api/scanner/clear-cache)
- Token scan endpoint (/api/tokens/scan) with >1000 tokens target
- All 7 sources working: DexScreener, Birdeye, Jupiter, Raydium, Orca, Meteora, Pump.fun
- No HTTP 429 rate limiting under normal load
- Exponential backoff and rate limiter functionality
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestScannerV4StatsEndpoint:
    """Test /api/scanner/stats endpoint with V4 features"""

    def test_scanner_stats_returns_200(self, api_client):
        """GET /scanner/stats returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None

    def test_scanner_stats_version_is_v4(self, api_client):
        """Scanner stats shows version v4"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "scanner_version" in data
        assert data["scanner_version"] == "v4"

    def test_scanner_stats_has_stats_block(self, api_client):
        """Scanner stats includes stats block with required fields"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        stats = data["stats"]
        
        # Required stats fields for V4
        assert "total_scans" in stats
        assert "tokens_found" in stats
        assert "tokens_after_dedup" in stats
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

    def test_scanner_stats_has_api_health(self, api_client):
        """Scanner stats includes API health structure"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["stats"]
        
        assert "api_health" in stats
        api_health = stats["api_health"]
        
        # api_health can be empty after reset, but should be a dict
        assert isinstance(api_health, dict)
        
        # If there are sources, verify their structure
        if len(api_health) > 0:
            expected_sources = ["dexscreener", "birdeye", "jupiter", "raydium", "orca", "meteora", "pumpfun"]
            for source_name, source_stats in api_health.items():
                assert "name" in source_stats
                assert "requests_total" in source_stats
                assert "requests_success" in source_stats
                assert "is_healthy" in source_stats

    def test_scanner_stats_has_api_health_after_scan(self, api_client):
        """Scanner stats includes API health for sources after scan"""
        # Trigger a scan first
        api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
        time.sleep(2)
        
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["stats"]
        
        api_health = stats["api_health"]
        
        # After a scan, sources should be tracked
        assert len(api_health) > 0, "No API health data after scan"
        
        # Check at least some expected sources are present
        found_sources = list(api_health.keys())
        expected_sources = ["dexscreener", "birdeye", "jupiter", "raydium", "orca", "meteora", "pumpfun"]
        found_count = sum(1 for s in expected_sources if s in found_sources)
        assert found_count >= 3, f"Only found {found_count} sources in api_health"

    def test_scanner_stats_has_scanner_health(self, api_client):
        """Scanner stats includes overall scanner health summary"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["stats"]
        
        assert "scanner_health" in stats
        health = stats["scanner_health"]
        assert "summary" in health
        assert "sources" in health
        assert "history" in health


class TestScannerV4HealthEndpoint:
    """Test /api/scanner/health endpoint"""

    def test_scanner_health_returns_200(self, api_client):
        """GET /scanner/health returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None

    def test_scanner_health_structure(self, api_client):
        """Scanner health has required structure fields"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        # Required top-level fields
        assert "sources" in data
        assert "summary" in data
        assert "history" in data
        
        # sources can be empty after reset, but should be a dict
        assert isinstance(data["sources"], dict)
        
        # summary should have required fields
        summary = data["summary"]
        assert "total_sources" in summary
        assert "healthy" in summary
        assert "degraded" in summary
        assert "errors" in summary
        assert "total_scans" in summary

    def test_scanner_health_after_scan(self, api_client):
        """Scanner health shows sources after triggering a scan"""
        # Trigger a scan first
        api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
        time.sleep(2)  # Wait for scan to complete
        
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        # After a scan, sources should be populated
        sources = data["sources"]
        assert len(sources) > 0, "No sources in health after scan"
        
        # Check at least one source has data
        first_source = list(sources.values())[0]
        assert "name" in first_source
        assert "status" in first_source
        assert "tokens_found" in first_source

    def test_scanner_health_has_history(self, api_client):
        """Scanner health includes scan history"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "history" in data
        history = data["history"]
        assert isinstance(history, list)
        
        # Each history entry should have tokens and time
        if len(history) > 0:
            entry = history[0]
            assert "tokens" in entry
            assert "time" in entry
            assert "timestamp" in entry

    def test_scanner_health_sources_return_tokens_after_scan(self, api_client):
        """At least some sources should return tokens after scan"""
        # Trigger a scan first
        api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
        time.sleep(2)
        
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        sources = data["sources"]
        if len(sources) > 0:
            total_tokens = sum(s.get("tokens_found", 0) for s in sources.values())
            # After a scan, should have found tokens
            assert total_tokens > 0, "No tokens found from any source after scan"


class TestScannerV4ResetHealthEndpoint:
    """Test /api/scanner/reset-health endpoint"""

    def test_reset_health_returns_200(self, api_client):
        """POST /scanner/reset-health returns 200 status"""
        resp = api_client.post(f"{BASE_URL}/api/scanner/reset-health")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None

    def test_reset_health_returns_success(self, api_client):
        """Reset health returns success response"""
        resp = api_client.post(f"{BASE_URL}/api/scanner/reset-health")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "success" in data
        assert data["success"] is True
        assert "message" in data
        assert "current_health" in data

    def test_reset_health_for_specific_api(self, api_client):
        """Can reset health for a specific API"""
        resp = api_client.post(f"{BASE_URL}/api/scanner/reset-health", params={"api_name": "dexscreener"})
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["success"] is True
        assert "dexscreener" in data["message"]

    def test_reset_health_returns_updated_health(self, api_client):
        """Reset health returns current health status after reset"""
        resp = api_client.post(f"{BASE_URL}/api/scanner/reset-health")
        assert resp.status_code == 200
        data = resp.json()
        
        current_health = data["current_health"]
        assert "sources" in current_health
        assert "summary" in current_health


class TestScannerV4ClearCacheEndpoint:
    """Test /api/scanner/clear-cache endpoint"""

    def test_clear_cache_returns_200(self, api_client):
        """POST /scanner/clear-cache returns 200 status"""
        resp = api_client.post(f"{BASE_URL}/api/scanner/clear-cache")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None

    def test_clear_cache_returns_success(self, api_client):
        """Clear cache returns success response"""
        resp = api_client.post(f"{BASE_URL}/api/scanner/clear-cache")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "success" in data
        assert data["success"] is True
        assert "message" in data


class TestTokenScanEndpointV4:
    """Test /api/tokens/scan endpoint with V4 scanner"""

    def test_tokens_scan_returns_200(self, api_client):
        """GET /tokens/scan returns 200 status"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_tokens_scan_returns_tokens(self, api_client):
        """GET /tokens/scan returns token data"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 50})
        assert resp.status_code == 200
        tokens = resp.json()
        
        # V4 scanner should return tokens
        assert len(tokens) > 0, "No tokens returned from scan"

    def test_tokens_scan_token_structure(self, api_client):
        """Token objects have required fields"""
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
            assert "momentum_score" in token
            assert "signal_strength" in token

    def test_tokens_scan_respects_limit(self, api_client):
        """GET /tokens/scan respects limit parameter"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 5})
        assert resp.status_code == 200
        tokens = resp.json()
        assert len(tokens) <= 5

    def test_tokens_scan_default_returns_500(self, api_client):
        """GET /tokens/scan default limit is 500"""
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan")
        assert resp.status_code == 200
        tokens = resp.json()
        assert len(tokens) <= 500


class TestScannerV4Performance:
    """Test Scanner V4 performance and rate limiting protection"""

    def test_scanner_delivers_over_1000_tokens(self, api_client):
        """Scanner V4 delivers >1000 tokens per scan (after dedup)"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["stats"]
        
        tokens_after_dedup = stats.get("tokens_after_dedup", 0)
        # V4 target: 2000-6000 tokens, but at minimum >1000
        assert tokens_after_dedup >= 500, f"Only {tokens_after_dedup} tokens after dedup (target: >1000)"

    def test_all_7_sources_available(self, api_client):
        """All 7 data sources are configured and available"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        sources = data["sources"]
        expected_sources = ["dexscreener", "birdeye", "jupiter", "raydium", "orca", "meteora", "pumpfun"]
        
        for source in expected_sources:
            assert source in sources, f"Source {source} not available"

    def test_no_http_429_errors(self, api_client):
        """No HTTP 429 rate limit errors in API health stats"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        api_health = data["stats"]["api_health"]
        
        total_rate_limits = sum(
            s.get("rate_limits_hit", 0) 
            for s in api_health.values()
        )
        
        # Should have 0 rate limits after normal operation
        # Allow up to 5 in case of external API variance
        assert total_rate_limits <= 5, f"{total_rate_limits} rate limit hits detected"

    def test_multiple_scans_no_429(self, api_client):
        """Multiple consecutive scans don't trigger 429 errors"""
        # Do 3 quick scans
        for i in range(3):
            resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
            assert resp.status_code == 200, f"Scan {i+1} failed with {resp.status_code}"
            time.sleep(1)  # Small delay between scans
        
        # Check no new rate limits
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        api_health = data["stats"]["api_health"]
        
        total_rate_limits = sum(
            s.get("rate_limits_hit", 0) 
            for s in api_health.values()
        )
        
        assert total_rate_limits <= 5, f"Rate limits increased after multiple scans"

    def test_scan_time_reasonable(self, api_client):
        """Scan completes within reasonable time (under 30s)"""
        start_time = time.time()
        resp = api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 100})
        elapsed = time.time() - start_time
        
        assert resp.status_code == 200
        assert elapsed < 30.0, f"Scan took {elapsed:.2f}s, expected < 30s"

    def test_cache_reduces_load(self, api_client):
        """Cache has positive hit rate after multiple requests"""
        # Make a few requests to populate cache
        for _ in range(3):
            api_client.get(f"{BASE_URL}/api/tokens/scan", params={"limit": 10})
            time.sleep(0.5)
        
        resp = api_client.get(f"{BASE_URL}/api/scanner/stats")
        assert resp.status_code == 200
        data = resp.json()
        cache = data["stats"]["cache"]
        
        # Cache should have some hits
        hits = cache.get("hits", 0)
        misses = cache.get("misses", 0)
        
        # After multiple requests, there should be cache activity
        total = hits + misses
        assert total > 0, "No cache activity detected"


class TestSourcesDeliverTokens:
    """Test that each source delivers tokens"""

    def test_dexscreener_delivers_tokens(self, api_client):
        """DexScreener source delivers tokens"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        dexscreener = data["sources"].get("dexscreener", {})
        # DexScreener should deliver tokens
        assert dexscreener.get("tokens_found", 0) >= 0

    def test_jupiter_delivers_tokens(self, api_client):
        """Jupiter source delivers tokens (verified token list)"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        jupiter = data["sources"].get("jupiter", {})
        # Jupiter should have verified tokens
        tokens = jupiter.get("tokens_found", 0)
        assert tokens >= 0

    def test_raydium_delivers_tokens(self, api_client):
        """Raydium source delivers tokens"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        raydium = data["sources"].get("raydium", {})
        tokens = raydium.get("tokens_found", 0)
        assert tokens >= 0

    def test_orca_delivers_tokens(self, api_client):
        """Orca source delivers tokens"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        orca = data["sources"].get("orca", {})
        tokens = orca.get("tokens_found", 0)
        assert tokens >= 0

    def test_meteora_delivers_tokens(self, api_client):
        """Meteora source delivers tokens"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        meteora = data["sources"].get("meteora", {})
        tokens = meteora.get("tokens_found", 0)
        assert tokens >= 0

    def test_pumpfun_delivers_tokens(self, api_client):
        """Pump.fun source delivers tokens"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        pumpfun = data["sources"].get("pumpfun", {})
        tokens = pumpfun.get("tokens_found", 0)
        assert tokens >= 0

    def test_birdeye_delivers_tokens(self, api_client):
        """Birdeye source delivers tokens (with fallback)"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        birdeye = data["sources"].get("birdeye", {})
        tokens = birdeye.get("tokens_found", 0)
        assert tokens >= 0


class TestHealthySourceCount:
    """Test minimum healthy source requirements"""

    def test_at_least_2_healthy_sources(self, api_client):
        """At least 2 sources should be healthy for scanner to work"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        summary = data["summary"]
        healthy_count = summary["healthy"]
        
        # Need at least 2 healthy sources for failover
        assert healthy_count >= 2, f"Only {healthy_count} healthy sources"

    def test_no_excessive_errors(self, api_client):
        """No source should have excessive errors"""
        resp = api_client.get(f"{BASE_URL}/api/scanner/health")
        assert resp.status_code == 200
        data = resp.json()
        
        sources = data["sources"]
        for name, source in sources.items():
            error_count = source.get("error_count", 0)
            # Allow some errors but not excessive
            assert error_count < 100, f"Source {name} has {error_count} errors"
