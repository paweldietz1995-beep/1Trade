"""
Rate Limiter & Exponential Backoff für API-Anfragen

Features:
- Token Bucket Rate Limiting (max 8-10 Requests/Sekunde pro API)
- Exponential Backoff bei HTTP 429 (1s -> 2s -> 4s -> 8s, max 5 Retries)
- Per-API Tracking und Health Status
"""

import asyncio
import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class APIStats:
    """Statistiken für eine einzelne API"""
    name: str
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    rate_limits_hit: int = 0
    last_request: Optional[float] = None
    last_success: Optional[float] = None
    last_rate_limit: Optional[float] = None
    consecutive_failures: int = 0
    is_healthy: bool = True
    backoff_until: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_failed": self.requests_failed,
            "rate_limits_hit": self.rate_limits_hit,
            "success_rate": round((self.requests_success / max(self.requests_total, 1)) * 100, 1),
            "consecutive_failures": self.consecutive_failures,
            "is_healthy": self.is_healthy,
            "in_backoff": self.backoff_until is not None and time.time() < self.backoff_until
        }


class ExponentialBackoff:
    """
    Exponential Backoff Handler
    
    Bei HTTP 429: 1s -> 2s -> 4s -> 8s -> 16s
    Max 5 Retries, dann API als unhealthy markieren
    """
    
    def __init__(self, base_delay: float = 1.0, max_retries: int = 5, max_delay: float = 16.0):
        self.base_delay = base_delay
        self.max_retries = max_retries
        self.max_delay = max_delay
        self._retry_counts: Dict[str, int] = {}
        self._backoff_until: Dict[str, float] = {}
    
    def get_delay(self, api_name: str) -> float:
        """Berechnet die aktuelle Backoff-Verzögerung"""
        retry_count = self._retry_counts.get(api_name, 0)
        if retry_count == 0:
            return 0
        
        delay = self.base_delay * (2 ** (retry_count - 1))
        return min(delay, self.max_delay)
    
    def record_failure(self, api_name: str) -> tuple:
        """
        Registriert einen Fehler und berechnet Backoff
        
        Returns: (should_retry, delay, retry_count)
        """
        self._retry_counts[api_name] = self._retry_counts.get(api_name, 0) + 1
        retry_count = self._retry_counts[api_name]
        
        if retry_count > self.max_retries:
            return (False, 0, retry_count)
        
        delay = self.get_delay(api_name)
        self._backoff_until[api_name] = time.time() + delay
        
        logger.warning(f"⚠️ BACKOFF [{api_name}]: Retry {retry_count}/{self.max_retries}, warte {delay:.1f}s")
        
        return (True, delay, retry_count)
    
    def record_success(self, api_name: str):
        """Setzt den Retry-Counter bei Erfolg zurück"""
        if api_name in self._retry_counts:
            self._retry_counts[api_name] = 0
        if api_name in self._backoff_until:
            del self._backoff_until[api_name]
    
    def is_in_backoff(self, api_name: str) -> bool:
        """Prüft ob API noch im Backoff ist"""
        if api_name not in self._backoff_until:
            return False
        return time.time() < self._backoff_until[api_name]
    
    def get_remaining_backoff(self, api_name: str) -> float:
        """Gibt verbleibende Backoff-Zeit zurück"""
        if api_name not in self._backoff_until:
            return 0
        remaining = self._backoff_until[api_name] - time.time()
        return max(0, remaining)
    
    def reset(self, api_name: str):
        """Setzt Backoff für eine API komplett zurück"""
        self._retry_counts[api_name] = 0
        if api_name in self._backoff_until:
            del self._backoff_until[api_name]
    
    def reset_all(self):
        """Setzt alle Backoffs zurück"""
        self._retry_counts.clear()
        self._backoff_until.clear()


class RateLimiter:
    """
    Token Bucket Rate Limiter
    
    Limitiert Requests auf max 8-10 pro Sekunde pro API.
    Verhindert aggressive Anfragen die zu 429 führen.
    """
    
    def __init__(self, requests_per_second: float = 8.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self._last_request: Dict[str, float] = {}
        self._request_counts: Dict[str, list] = {}  # Sliding window
        self._lock = asyncio.Lock()
    
    async def acquire(self, api_name: str) -> float:
        """
        Wartet bis eine Anfrage erlaubt ist.
        
        Returns: Wartezeit in Sekunden
        """
        async with self._lock:
            now = time.time()
            
            # Sliding window: Entferne alte Requests (älter als 1 Sekunde)
            if api_name not in self._request_counts:
                self._request_counts[api_name] = []
            
            self._request_counts[api_name] = [
                t for t in self._request_counts[api_name] 
                if now - t < 1.0
            ]
            
            # Prüfe ob Limit erreicht
            if len(self._request_counts[api_name]) >= self.requests_per_second:
                # Warte bis ältester Request aus dem Fenster fällt
                oldest = min(self._request_counts[api_name])
                wait_time = 1.0 - (now - oldest) + 0.05  # +50ms Buffer
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    # Bereinige nochmal
                    self._request_counts[api_name] = [
                        t for t in self._request_counts[api_name] 
                        if now - t < 1.0
                    ]
            
            # Registriere diesen Request
            self._request_counts[api_name].append(now)
            self._last_request[api_name] = now
            
            return 0
    
    def get_stats(self, api_name: str) -> dict:
        """Gibt Rate-Limit-Statistiken zurück"""
        now = time.time()
        recent = [t for t in self._request_counts.get(api_name, []) if now - t < 1.0]
        return {
            "api_name": api_name,
            "requests_last_second": len(recent),
            "max_per_second": self.requests_per_second,
            "utilization": round(len(recent) / self.requests_per_second * 100, 1)
        }


class APIHealthTracker:
    """
    Verfolgt den Gesundheitszustand aller APIs
    
    Eine API wird als unhealthy markiert wenn:
    - 5 aufeinanderfolgende Fehler
    - Rate-Limit 3x in 60 Sekunden
    """
    
    def __init__(self):
        self._stats: Dict[str, APIStats] = {}
        self._rate_limit_history: Dict[str, list] = {}
        self.backoff = ExponentialBackoff()
        self.rate_limiter = RateLimiter(requests_per_second=8.0)
        
    def _get_stats(self, api_name: str) -> APIStats:
        if api_name not in self._stats:
            self._stats[api_name] = APIStats(name=api_name)
        return self._stats[api_name]
    
    def record_request(self, api_name: str):
        """Registriert einen API-Request"""
        stats = self._get_stats(api_name)
        stats.requests_total += 1
        stats.last_request = time.time()
    
    def record_success(self, api_name: str):
        """Registriert einen erfolgreichen Request"""
        stats = self._get_stats(api_name)
        stats.requests_success += 1
        stats.last_success = time.time()
        stats.consecutive_failures = 0
        stats.is_healthy = True
        stats.backoff_until = None
        self.backoff.record_success(api_name)
    
    def record_failure(self, api_name: str, is_rate_limit: bool = False) -> tuple:
        """
        Registriert einen fehlgeschlagenen Request
        
        Returns: (should_retry, delay)
        """
        stats = self._get_stats(api_name)
        stats.requests_failed += 1
        stats.consecutive_failures += 1
        
        if is_rate_limit:
            stats.rate_limits_hit += 1
            stats.last_rate_limit = time.time()
            
            # Track rate-limit history
            if api_name not in self._rate_limit_history:
                self._rate_limit_history[api_name] = []
            self._rate_limit_history[api_name].append(time.time())
            
            # Clean old entries (> 60s)
            self._rate_limit_history[api_name] = [
                t for t in self._rate_limit_history[api_name]
                if time.time() - t < 60
            ]
            
            # Mark unhealthy if 3+ rate limits in 60s
            if len(self._rate_limit_history[api_name]) >= 3:
                stats.is_healthy = False
                logger.warning(f"🚫 API [{api_name}] als UNHEALTHY markiert (3+ Rate-Limits in 60s)")
        
        # Mark unhealthy if 5 consecutive failures
        if stats.consecutive_failures >= 5:
            stats.is_healthy = False
            logger.warning(f"🚫 API [{api_name}] als UNHEALTHY markiert (5 konsekutive Fehler)")
        
        # Calculate backoff
        should_retry, delay, _ = self.backoff.record_failure(api_name)
        if delay > 0:
            stats.backoff_until = time.time() + delay
        
        return (should_retry, delay)
    
    def is_healthy(self, api_name: str) -> bool:
        """Prüft ob eine API gesund ist"""
        stats = self._get_stats(api_name)
        
        # Check if in backoff
        if self.backoff.is_in_backoff(api_name):
            return False
        
        return stats.is_healthy
    
    def reset_health(self, api_name: str):
        """Setzt den Gesundheitszustand einer API zurück"""
        stats = self._get_stats(api_name)
        stats.is_healthy = True
        stats.consecutive_failures = 0
        stats.backoff_until = None
        self.backoff.reset(api_name)
        if api_name in self._rate_limit_history:
            self._rate_limit_history[api_name] = []
        logger.info(f"✅ API [{api_name}] Gesundheit zurückgesetzt")
    
    def get_all_stats(self) -> dict:
        """Gibt Statistiken für alle APIs zurück"""
        return {
            name: stats.to_dict() 
            for name, stats in self._stats.items()
        }
    
    def get_healthy_apis(self) -> list:
        """Gibt Liste aller gesunden APIs zurück"""
        return [
            name for name, stats in self._stats.items()
            if stats.is_healthy and not self.backoff.is_in_backoff(name)
        ]


# Global instances
api_health = APIHealthTracker()
