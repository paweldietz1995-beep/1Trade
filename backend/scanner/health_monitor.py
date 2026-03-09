"""
Scanner Health Monitor

Überwacht und loggt den Gesundheitszustand aller Scanner-Quellen.
Generiert SCANNER HEALTH Logs wie vom Benutzer angefordert.
"""

import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SourceHealth:
    """Gesundheitszustand einer einzelnen Quelle"""
    name: str
    status: str = "UNKNOWN"  # OK, DEGRADED, DOWN, UNKNOWN
    tokens_found: int = 0
    last_scan_time: float = 0
    error_count: int = 0
    rate_limit_count: int = 0
    last_error: Optional[str] = None
    last_update: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "tokens_found": self.tokens_found,
            "last_scan_time_ms": round(self.last_scan_time * 1000, 1),
            "error_count": self.error_count,
            "rate_limit_count": self.rate_limit_count,
            "last_error": self.last_error
        }


class ScannerHealthMonitor:
    """
    Zentraler Health Monitor für alle Scanner-Quellen
    
    Generiert SCANNER HEALTH Logs:
    - dexscreener_status
    - birdeye_status
    - raydium_status
    - orca_status
    - meteora_status
    - jupiter_status
    - pumpfun_status
    - tokens_total
    - scan_time
    """
    
    def __init__(self):
        self._sources: Dict[str, SourceHealth] = {}
        self._scan_history: list = []
        self._total_scans = 0
        self._last_scan_time: Optional[float] = None
        self._last_tokens_total = 0
    
    def _get_source(self, name: str) -> SourceHealth:
        if name not in self._sources:
            self._sources[name] = SourceHealth(name=name)
        return self._sources[name]
    
    def record_scan_start(self):
        """Markiert den Start eines Scan-Zyklus"""
        self._scan_start = time.time()
        self._total_scans += 1
    
    def record_source_result(self, source_name: str, tokens_count: int, scan_time: float, error: str = None):
        """
        Registriert das Ergebnis eines Quellen-Scans
        
        Args:
            source_name: Name der Quelle (dexscreener, birdeye, etc.)
            tokens_count: Anzahl gefundener Tokens
            scan_time: Scan-Zeit in Sekunden
            error: Optionaler Fehler
        """
        source = self._get_source(source_name)
        source.tokens_found = tokens_count
        source.last_scan_time = scan_time
        source.last_update = time.time()
        
        if error:
            source.error_count += 1
            source.last_error = error
            if "429" in str(error) or "rate" in str(error).lower():
                source.rate_limit_count += 1
                source.status = "RATE_LIMITED"
            else:
                source.status = "ERROR"
        elif tokens_count == 0:
            source.status = "DEGRADED"
        else:
            source.status = "OK"
            source.last_error = None
    
    def record_scan_complete(self, total_tokens: int, scan_time: float):
        """
        Markiert das Ende eines Scan-Zyklus und loggt Health-Status
        
        Args:
            total_tokens: Gesamtzahl der gefundenen Tokens
            scan_time: Gesamte Scan-Zeit in Sekunden
        """
        self._last_scan_time = scan_time
        self._last_tokens_total = total_tokens
        
        # Store in history (keep last 20)
        self._scan_history.append({
            "tokens": total_tokens,
            "time": scan_time,
            "timestamp": time.time()
        })
        if len(self._scan_history) > 20:
            self._scan_history = self._scan_history[-20:]
        
        # Generate Health Log
        self._log_health_status()
    
    def _log_health_status(self):
        """Generiert das SCANNER HEALTH Log"""
        logger.info("=" * 70)
        logger.info("📊 SCANNER HEALTH")
        
        # Source statuses
        for name in ["dexscreener", "birdeye", "raydium", "orca", "meteora", "jupiter", "pumpfun"]:
            source = self._sources.get(name)
            if source:
                status_emoji = {
                    "OK": "✅",
                    "DEGRADED": "⚠️",
                    "RATE_LIMITED": "🚫",
                    "ERROR": "❌",
                    "UNKNOWN": "❓"
                }.get(source.status, "❓")
                logger.info(f"   {name}_status: {status_emoji} {source.status} ({source.tokens_found} tokens)")
            else:
                logger.info(f"   {name}_status: ❓ NOT_INITIALIZED")
        
        logger.info(f"   ─────────────────")
        logger.info(f"   tokens_total: {self._last_tokens_total}")
        logger.info(f"   scan_time: {self._last_scan_time:.2f}s")
        
        # Calculate averages
        if self._scan_history:
            avg_tokens = sum(h["tokens"] for h in self._scan_history) / len(self._scan_history)
            avg_time = sum(h["time"] for h in self._scan_history) / len(self._scan_history)
            logger.info(f"   avg_tokens: {avg_tokens:.0f}")
            logger.info(f"   avg_scan_time: {avg_time:.2f}s")
        
        logger.info("=" * 70)
    
    def get_health_summary(self) -> dict:
        """Gibt eine Zusammenfassung des Gesundheitszustands zurück"""
        healthy_count = sum(1 for s in self._sources.values() if s.status == "OK")
        degraded_count = sum(1 for s in self._sources.values() if s.status == "DEGRADED")
        error_count = sum(1 for s in self._sources.values() if s.status in ["ERROR", "RATE_LIMITED"])
        
        return {
            "sources": {name: source.to_dict() for name, source in self._sources.items()},
            "summary": {
                "total_sources": len(self._sources),
                "healthy": healthy_count,
                "degraded": degraded_count,
                "errors": error_count,
                "total_scans": self._total_scans,
                "last_tokens_total": self._last_tokens_total,
                "last_scan_time": self._last_scan_time
            },
            "history": self._scan_history[-10:]  # Last 10 scans
        }
    
    def is_scanner_healthy(self) -> bool:
        """Prüft ob der Scanner insgesamt gesund ist"""
        if not self._sources:
            return False
        
        healthy_count = sum(1 for s in self._sources.values() if s.status == "OK")
        return healthy_count >= 2  # Mindestens 2 gesunde Quellen
    
    def get_working_sources(self) -> list:
        """Gibt Liste der funktionierenden Quellen zurück"""
        return [
            name for name, source in self._sources.items()
            if source.status in ["OK", "DEGRADED"]
        ]
    
    def reset_source(self, source_name: str):
        """Setzt den Status einer Quelle zurück"""
        if source_name in self._sources:
            source = self._sources[source_name]
            source.status = "UNKNOWN"
            source.error_count = 0
            source.rate_limit_count = 0
            source.last_error = None
            logger.info(f"✅ Quelle [{source_name}] zurückgesetzt")


# Global instance
scanner_health = ScannerHealthMonitor()
