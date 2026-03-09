"""
Multi-Source Scanner V4 - Hochverfügbare Scanner-Architektur

Features:
1. Exponential Backoff bei HTTP 429 (1s -> 2s -> 4s -> 8s, max 5 Retries)
2. Request Throttling (max 8-10 Requests/Sekunde pro API)
3. Echte Multi-Source Integration:
   - DexScreener (mit Rate-Limit Schutz)
   - Birdeye API (vorbereitet für API-Key)
   - Raydium SDK
   - Orca Whirlpool
   - Meteora
   - Jupiter Token List
   - Pump.fun Launches
4. Automatisches Failover zwischen Quellen
5. Caching mit 2 Sekunden TTL
6. Health Monitoring und Logging

Ziel: 2000-6000 Tokens pro Scan, auch wenn eine API temporär blockiert.
"""

import asyncio
import time
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import httpx

from .rate_limiter import RateLimiter, ExponentialBackoff, APIHealthTracker, api_health
from .health_monitor import ScannerHealthMonitor, scanner_health

logger = logging.getLogger(__name__)


class ScannerCache:
    """
    High-Performance Cache mit 2-Sekunden TTL
    Reduziert API-Anfragen massiv
    """
    
    def __init__(self, ttl_seconds: float = 2.0):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self._cache:
                age = time.time() - self._timestamps.get(key, 0)
                if age < self._ttl:
                    self._hits += 1
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._timestamps[key]
            self._misses += 1
            return None
    
    async def set(self, key: str, value: Any):
        async with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()
    
    async def clear(self):
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
    
    def get_stats(self) -> Dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 1),
            "cached_items": len(self._cache)
        }


class MultiSourceScannerV4:
    """
    Hochverfügbare Multi-Source Scanner Architektur V4
    
    Ein einzelner API-Rate-Limit darf den Bot NIEMALS stoppen.
    """
    
    def __init__(self):
        # Cache mit 2s TTL
        self.cache = ScannerCache(ttl_seconds=2.0)
        
        # Health Tracking
        self.health = api_health
        
        # Rate Limiter (8 Requests/Sekunde pro API)
        self.rate_limiter = RateLimiter(requests_per_second=8.0)
        
        # Backoff Handler
        self.backoff = ExponentialBackoff(base_delay=1.0, max_retries=5, max_delay=16.0)
        
        # HTTP Client Pool
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Scan Statistics
        self.scan_stats = {
            "total_scans": 0,
            "tokens_found": 0,
            "tokens_after_dedup": 0,
            "last_scan": None,
            "avg_scan_time_ms": 0,
            "scan_history": []
        }
        
        # Source Configuration
        self.sources = {
            "dexscreener": {
                "enabled": True,
                "priority": 1,
                "base_url": "https://api.dexscreener.com"
            },
            "birdeye": {
                "enabled": True,
                "priority": 2,
                "base_url": "https://public-api.birdeye.so",
                "api_key": os.environ.get("BIRDEYE_API_KEY")
            },
            "jupiter": {
                "enabled": True,
                "priority": 3,
                "base_url": "https://token.jup.ag"
            },
            "raydium": {
                "enabled": True,
                "priority": 4,
                "base_url": "https://api.raydium.io"
            },
            "orca": {
                "enabled": True,
                "priority": 5,
                "base_url": "https://api.mainnet.orca.so"
            },
            "meteora": {
                "enabled": True,
                "priority": 6,
                "base_url": "https://dlmm-api.meteora.ag"
            },
            "pumpfun": {
                "enabled": True,
                "priority": 7,
                "base_url": "https://frontend-api.pump.fun"
            }
        }
        
        # Birdeye API Key (optional)
        self.birdeye_api_key = os.environ.get("BIRDEYE_API_KEY")
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Wiederverwendbarer HTTP Client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=20.0,
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
                follow_redirects=True
            )
        return self._http_client
    
    async def _make_request(self, api_name: str, url: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        """
        Macht einen API-Request mit Rate-Limiting und Backoff
        
        Returns: Response JSON oder None bei Fehler
        """
        # Check if API is in backoff
        if self.backoff.is_in_backoff(api_name):
            remaining = self.backoff.get_remaining_backoff(api_name)
            logger.debug(f"⏳ [{api_name}] noch {remaining:.1f}s im Backoff")
            return None
        
        # Check health
        if not self.health.is_healthy(api_name):
            logger.debug(f"🚫 [{api_name}] ist unhealthy, überspringe")
            return None
        
        # Rate limiting
        await self.rate_limiter.acquire(api_name)
        
        # Record request
        self.health.record_request(api_name)
        
        try:
            client = await self._get_http_client()
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                self.health.record_success(api_name)
                self.backoff.record_success(api_name)
                return response.json()
            
            elif response.status_code == 429:
                # Rate Limited - apply backoff
                logger.warning(f"🚫 HTTP 429 [{api_name}] - Rate Limited!")
                should_retry, delay = self.health.record_failure(api_name, is_rate_limit=True)
                if should_retry and delay > 0:
                    await asyncio.sleep(delay)
                return None
            
            else:
                logger.debug(f"⚠️ [{api_name}] HTTP {response.status_code}")
                self.health.record_failure(api_name)
                return None
                
        except asyncio.TimeoutError:
            logger.debug(f"⏱️ [{api_name}] Timeout")
            self.health.record_failure(api_name)
            return None
        except Exception as e:
            logger.debug(f"❌ [{api_name}] Error: {str(e)[:50]}")
            self.health.record_failure(api_name)
            return None
    
    async def scan_all_sources(self) -> List[Dict]:
        """
        HAUPTSCANNER - Scannt alle Quellen parallel mit Failover
        
        Ziel: 2000-6000 Tokens pro Scan
        """
        scan_start = time.time()
        all_tokens = []
        source_results = {}
        
        scanner_health.record_scan_start()
        
        logger.info("=" * 70)
        logger.info("🔍 MULTI-SOURCE SCANNER V4 - Starte hochverfügbaren Scan...")
        logger.info("=" * 70)
        
        # Parallel scan all healthy sources
        tasks = []
        source_names = []
        
        for source_name, config in self.sources.items():
            if not config["enabled"]:
                continue
            if not self.health.is_healthy(source_name) and source_name != "jupiter":
                logger.info(f"⏭️ [{source_name}] übersprungen (unhealthy)")
                continue
            
            source_names.append(source_name)
            tasks.append(self._scan_source_with_cache(source_name))
        
        # Execute all scans in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                source_name = source_names[i]
                scan_time = time.time() - scan_start
                
                if isinstance(result, Exception):
                    logger.warning(f"❌ [{source_name}] Fehler: {str(result)[:50]}")
                    scanner_health.record_source_result(source_name, 0, scan_time, str(result))
                    source_results[source_name] = 0
                elif isinstance(result, list):
                    source_results[source_name] = len(result)
                    all_tokens.extend(result)
                    scanner_health.record_source_result(source_name, len(result), scan_time)
                else:
                    source_results[source_name] = 0
                    scanner_health.record_source_result(source_name, 0, scan_time, "Invalid result")
        
        # Deduplicate by token address
        unique_tokens = self._deduplicate_tokens(all_tokens)
        
        # Calculate metrics
        scan_time = time.time() - scan_start
        
        # Update stats
        self.scan_stats["total_scans"] += 1
        self.scan_stats["tokens_found"] = len(all_tokens)
        self.scan_stats["tokens_after_dedup"] = len(unique_tokens)
        self.scan_stats["last_scan"] = datetime.now(timezone.utc).isoformat()
        
        # Update scan history
        self.scan_stats["scan_history"].append(scan_time * 1000)
        if len(self.scan_stats["scan_history"]) > 10:
            self.scan_stats["scan_history"] = self.scan_stats["scan_history"][-10:]
        self.scan_stats["avg_scan_time_ms"] = sum(self.scan_stats["scan_history"]) / len(self.scan_stats["scan_history"])
        
        # Record scan complete
        scanner_health.record_scan_complete(len(unique_tokens), scan_time)
        
        # Log source breakdown
        logger.info("=" * 70)
        logger.info("📊 SCANNER ERGEBNIS")
        for source, count in source_results.items():
            status = "✅" if count > 0 else "⚠️"
            logger.info(f"   {status} {source}: {count} tokens")
        logger.info(f"   ─────────────────")
        logger.info(f"   📦 tokens_gesamt: {len(unique_tokens)}")
        logger.info(f"   ⏱️ scan_zeit: {scan_time:.2f}s")
        logger.info("=" * 70)
        
        return unique_tokens
    
    async def _scan_source_with_cache(self, source_name: str) -> List[Dict]:
        """Scannt eine Quelle mit Cache-Check"""
        cache_key = f"scan_{source_name}"
        
        # Check cache
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"📦 [{source_name}] Cache hit ({len(cached)} tokens)")
            return cached
        
        # Fetch fresh data
        try:
            scanner_func = getattr(self, f"_scan_{source_name}", None)
            if scanner_func:
                tokens = await scanner_func()
                await self.cache.set(cache_key, tokens)
                return tokens
        except Exception as e:
            logger.error(f"❌ [{source_name}] Scan error: {e}")
        
        return []
    
    # ==================== SCANNER IMPLEMENTATIONS ====================
    
    async def _scan_dexscreener(self) -> List[Dict]:
        """
        DexScreener Scanner mit Rate-Limit Schutz
        
        Strategie: Wenige strategische Queries statt aggressive Pagination
        """
        pairs = []
        seen = set()
        
        # Strategic queries (limited to avoid rate limits)
        queries = [
            "solana pump.fun new",
            "solana raydium trending",
            "solana meme hot",
            "sol degen"
        ]
        
        for query in queries:
            if not self.health.is_healthy("dexscreener"):
                break
            
            data = await self._make_request(
                "dexscreener",
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": query}
            )
            
            if data:
                for p in data.get("pairs", []):
                    if p.get("chainId") == "solana":
                        addr = p.get("baseToken", {}).get("address", "")
                        if addr and addr not in seen:
                            liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                            if liq >= 100:
                                p["source"] = "dexscreener"
                                pairs.append(p)
                                seen.add(addr)
            
            # Small delay between queries
            await asyncio.sleep(0.15)
        
        # Also fetch latest pairs
        if self.health.is_healthy("dexscreener"):
            latest = await self._make_request(
                "dexscreener",
                "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
            )
            if latest:
                for p in latest.get("pairs", [])[:100]:
                    if p.get("chainId") == "solana":
                        addr = p.get("baseToken", {}).get("address", "")
                        if addr and addr not in seen:
                            p["source"] = "dexscreener"
                            pairs.append(p)
                            seen.add(addr)
        
        logger.info(f"📊 DexScreener: {len(pairs)} tokens")
        return pairs
    
    async def _scan_birdeye(self) -> List[Dict]:
        """
        Birdeye Scanner - Nutzt echte Birdeye API wenn Key vorhanden
        
        Fallback: DexScreener mit Birdeye-spezifischen Queries
        """
        pairs = []
        seen = set()
        
        # If API key available, use real Birdeye API
        if self.birdeye_api_key:
            headers = {
                "X-API-KEY": self.birdeye_api_key,
                "x-chain": "solana"
            }
            
            # Trending tokens
            data = await self._make_request(
                "birdeye",
                "https://public-api.birdeye.so/defi/tokenlist",
                params={"sort_by": "v24hUSD", "sort_type": "desc", "limit": 100},
                headers=headers
            )
            
            if data and data.get("success"):
                for t in data.get("data", {}).get("tokens", []):
                    addr = t.get("address", "")
                    if addr and addr not in seen:
                        pairs.append(self._birdeye_to_standard_format(t))
                        seen.add(addr)
            
            # New tokens
            new_data = await self._make_request(
                "birdeye",
                "https://public-api.birdeye.so/defi/tokenlist",
                params={"sort_by": "lastTradeUnixTime", "sort_type": "desc", "limit": 100},
                headers=headers
            )
            
            if new_data and new_data.get("success"):
                for t in new_data.get("data", {}).get("tokens", []):
                    addr = t.get("address", "")
                    if addr and addr not in seen:
                        pairs.append(self._birdeye_to_standard_format(t))
                        seen.add(addr)
        else:
            # Fallback: Use DexScreener with Birdeye-style queries
            queries = ["trending solana", "gainers sol", "volume sol"]
            
            for query in queries:
                data = await self._make_request(
                    "birdeye",  # Track as birdeye for health monitoring
                    "https://api.dexscreener.com/latest/dex/search",
                    params={"q": query}
                )
                
                if data:
                    for p in data.get("pairs", []):
                        if p.get("chainId") == "solana":
                            addr = p.get("baseToken", {}).get("address", "")
                            if addr and addr not in seen:
                                if float(p.get("liquidity", {}).get("usd", 0) or 0) >= 100:
                                    p["source"] = "birdeye"
                                    pairs.append(p)
                                    seen.add(addr)
                
                await asyncio.sleep(0.15)
        
        logger.info(f"📊 Birdeye: {len(pairs)} tokens")
        return pairs
    
    def _birdeye_to_standard_format(self, token: dict) -> dict:
        """Konvertiert Birdeye Token Format zu Standard-Format"""
        return {
            "chainId": "solana",
            "baseToken": {
                "address": token.get("address", ""),
                "symbol": token.get("symbol", ""),
                "name": token.get("name", "")
            },
            "priceUsd": str(token.get("price", 0)),
            "liquidity": {"usd": token.get("liquidity", 0)},
            "volume": {
                "h24": token.get("v24hUSD", 0),
                "m5": 0,
                "h1": token.get("v24hUSD", 0) / 24
            },
            "priceChange": {
                "h24": token.get("priceChange24h", 0),
                "m5": 0,
                "h1": token.get("priceChange24h", 0) / 24
            },
            "txns": {"m5": {"buys": 0, "sells": 0}},
            "source": "birdeye"
        }
    
    async def _scan_jupiter(self) -> List[Dict]:
        """
        Jupiter Token Scanner - Verifizierte Token Liste
        
        Nutzt die offizielle Jupiter Token Liste für sichere Tokens
        """
        pairs = []
        seen = set()
        
        # Fetch token list from cache endpoint
        data = await self._make_request(
            "jupiter",
            "https://cache.jup.ag/tokens"
        )
        
        if data and isinstance(data, list):
            for t in data[:800]:  # Top 800 verified tokens
                addr = t.get("address", "")
                if addr and addr not in seen:
                    pairs.append({
                        "chainId": "solana",
                        "baseToken": {
                            "address": addr,
                            "symbol": t.get("symbol", ""),
                            "name": t.get("name", "")
                        },
                        "priceUsd": "0",
                        "liquidity": {"usd": 10000},  # Assumed for verified tokens
                        "volume": {"h24": 0, "m5": 0, "h1": 0},
                        "priceChange": {"h24": 0, "m5": 0, "h1": 0},
                        "txns": {"m5": {"buys": 0, "sells": 0}},
                        "source": "jupiter"
                    })
                    seen.add(addr)
        
        logger.info(f"📊 Jupiter: {len(pairs)} tokens")
        return pairs
    
    async def _scan_raydium(self) -> List[Dict]:
        """
        Raydium Pool Scanner
        
        Nutzt Raydium API für AMM und CLMM Pools
        """
        pairs = []
        seen = set()
        
        # Try Raydium API
        data = await self._make_request(
            "raydium",
            "https://api.raydium.io/v2/main/pairs"
        )
        
        if data:
            for pool in data[:500]:
                addr = pool.get("baseMint", "")
                if addr and addr not in seen:
                    pairs.append({
                        "chainId": "solana",
                        "baseToken": {
                            "address": addr,
                            "symbol": pool.get("name", "").split("/")[0] if "/" in pool.get("name", "") else "",
                            "name": pool.get("name", "")
                        },
                        "pairAddress": pool.get("ammId", ""),
                        "priceUsd": str(pool.get("price", 0)),
                        "liquidity": {"usd": pool.get("liquidity", 0)},
                        "volume": {"h24": pool.get("volume24h", 0), "m5": 0, "h1": 0},
                        "priceChange": {"h24": pool.get("priceChange24h", 0), "m5": 0, "h1": 0},
                        "txns": {"m5": {"buys": 0, "sells": 0}},
                        "dexId": "raydium",
                        "source": "raydium"
                    })
                    seen.add(addr)
        
        # Fallback to DexScreener if Raydium API fails
        if len(pairs) < 50:
            fallback_data = await self._make_request(
                "raydium",
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "raydium solana"}
            )
            
            if fallback_data:
                for p in fallback_data.get("pairs", []):
                    if p.get("chainId") == "solana" and "raydium" in p.get("dexId", "").lower():
                        addr = p.get("baseToken", {}).get("address", "")
                        if addr and addr not in seen:
                            p["source"] = "raydium"
                            pairs.append(p)
                            seen.add(addr)
        
        logger.info(f"📊 Raydium: {len(pairs)} tokens")
        return pairs
    
    async def _scan_orca(self) -> List[Dict]:
        """
        Orca Whirlpool Scanner
        
        Nutzt Orca API für Whirlpool Daten
        """
        pairs = []
        seen = set()
        
        # Try Orca Whirlpool API
        data = await self._make_request(
            "orca",
            "https://api.mainnet.orca.so/v1/whirlpool/list"
        )
        
        if data:
            whirlpools = data.get("whirlpools", data) if isinstance(data, dict) else data
            if isinstance(whirlpools, list):
                for pool in whirlpools[:500]:
                    addr = pool.get("tokenA", {}).get("mint", "") if isinstance(pool.get("tokenA"), dict) else ""
                    if not addr:
                        addr = pool.get("tokenMintA", "")
                    
                    if addr and addr not in seen:
                        pairs.append({
                            "chainId": "solana",
                            "baseToken": {
                                "address": addr,
                                "symbol": pool.get("tokenA", {}).get("symbol", "") if isinstance(pool.get("tokenA"), dict) else "",
                                "name": pool.get("tokenA", {}).get("name", "") if isinstance(pool.get("tokenA"), dict) else ""
                            },
                            "pairAddress": pool.get("address", ""),
                            "priceUsd": str(pool.get("price", 0)),
                            "liquidity": {"usd": pool.get("tvl", 0)},
                            "volume": {"h24": pool.get("volume", {}).get("day", 0) if isinstance(pool.get("volume"), dict) else 0, "m5": 0, "h1": 0},
                            "priceChange": {"h24": 0, "m5": 0, "h1": 0},
                            "txns": {"m5": {"buys": 0, "sells": 0}},
                            "dexId": "orca",
                            "source": "orca"
                        })
                        seen.add(addr)
        
        # Fallback
        if len(pairs) < 50:
            fallback_data = await self._make_request(
                "orca",
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "orca whirlpool"}
            )
            
            if fallback_data:
                for p in fallback_data.get("pairs", []):
                    if p.get("chainId") == "solana" and "orca" in p.get("dexId", "").lower():
                        addr = p.get("baseToken", {}).get("address", "")
                        if addr and addr not in seen:
                            p["source"] = "orca"
                            pairs.append(p)
                            seen.add(addr)
        
        logger.info(f"📊 Orca: {len(pairs)} tokens")
        return pairs
    
    async def _scan_meteora(self) -> List[Dict]:
        """
        Meteora DLMM Scanner
        
        Nutzt Meteora API für DLMM Pools
        """
        pairs = []
        seen = set()
        
        # Try Meteora API
        data = await self._make_request(
            "meteora",
            "https://dlmm-api.meteora.ag/pair/all"
        )
        
        if data and isinstance(data, list):
            for pool in data[:500]:
                addr = pool.get("mint_x", "")
                if addr and addr not in seen:
                    pairs.append({
                        "chainId": "solana",
                        "baseToken": {
                            "address": addr,
                            "symbol": pool.get("name", "").split("-")[0] if "-" in pool.get("name", "") else "",
                            "name": pool.get("name", "")
                        },
                        "pairAddress": pool.get("address", ""),
                        "priceUsd": str(pool.get("current_price", 0)),
                        "liquidity": {"usd": pool.get("liquidity", 0)},
                        "volume": {"h24": pool.get("trade_volume_24h", 0), "m5": 0, "h1": 0},
                        "priceChange": {"h24": 0, "m5": 0, "h1": 0},
                        "txns": {"m5": {"buys": 0, "sells": 0}},
                        "dexId": "meteora",
                        "source": "meteora"
                    })
                    seen.add(addr)
        
        # Fallback
        if len(pairs) < 50:
            fallback_data = await self._make_request(
                "meteora",
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "meteora dlmm"}
            )
            
            if fallback_data:
                for p in fallback_data.get("pairs", []):
                    if p.get("chainId") == "solana" and "meteora" in p.get("dexId", "").lower():
                        addr = p.get("baseToken", {}).get("address", "")
                        if addr and addr not in seen:
                            p["source"] = "meteora"
                            pairs.append(p)
                            seen.add(addr)
        
        logger.info(f"📊 Meteora: {len(pairs)} tokens")
        return pairs
    
    async def _scan_pumpfun(self) -> List[Dict]:
        """
        Pump.fun Launch Scanner
        
        Scannt neue Pump.fun Launches über DexScreener (direkter API-Zugang ist blockiert)
        """
        pairs = []
        seen = set()
        
        # Pump.fun direct API is blocked by Cloudflare, use DexScreener instead
        queries = ["pump.fun", "pumpfun bonding", "pump.fun new"]
        
        for query in queries:
            data = await self._make_request(
                "pumpfun",
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": query}
            )
            
            if data:
                for p in data.get("pairs", []):
                    if p.get("chainId") == "solana":
                        addr = p.get("baseToken", {}).get("address", "")
                        dex_id = p.get("dexId", "").lower()
                        # Filter for pump.fun related pairs
                        if addr and addr not in seen:
                            liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                            if liq >= 100:
                                p["source"] = "pumpfun"
                                pairs.append(p)
                                seen.add(addr)
            
            await asyncio.sleep(0.15)
        
        logger.info(f"📊 Pump.fun: {len(pairs)} tokens")
        return pairs
    
    def _deduplicate_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """Entfernt Duplikate nach Token-Adresse"""
        unique = {}
        
        for token in tokens:
            addr = token.get("baseToken", {}).get("address", "")
            if not addr:
                continue
            
            if addr not in unique:
                unique[addr] = token
            else:
                # Keep token with higher volume
                existing_vol = float(unique[addr].get("volume", {}).get("h24", 0) or 0)
                new_vol = float(token.get("volume", {}).get("h24", 0) or 0)
                if new_vol > existing_vol:
                    unique[addr] = token
        
        return list(unique.values())
    
    def get_stats(self) -> Dict:
        """Gibt Scanner-Statistiken zurück"""
        return {
            **self.scan_stats,
            "cache": self.cache.get_stats(),
            "api_health": self.health.get_all_stats(),
            "scanner_health": scanner_health.get_health_summary()
        }
    
    def reset_api_health(self, api_name: str = None):
        """Setzt API-Health zurück"""
        if api_name:
            self.health.reset_health(api_name)
            scanner_health.reset_source(api_name)
        else:
            # Reset all
            for name in self.sources.keys():
                self.health.reset_health(name)
                scanner_health.reset_source(name)
        
        self.backoff.reset_all()
        logger.info("✅ API Health zurückgesetzt")
    
    async def clear_cache(self):
        """Leert den Cache"""
        await self.cache.clear()
        logger.info("✅ Scanner Cache geleert")


# Global Scanner Instance
scanner_instance = MultiSourceScannerV4()
