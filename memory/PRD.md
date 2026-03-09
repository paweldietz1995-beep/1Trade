# Pump.fun Trading Bot - PRD v26

## Problem Statement
Automatisiertes Ultra-High-Frequency Trading-System für Pump.fun Tokens auf der Solana Blockchain mit Realtime Launch Sniper und 100+ simultanen Micro-Trades.

## System Status: MULTI-SOURCE SCANNER V4 AKTIV

Letztes Update: 2026-03-09

---

## Changelog

### 2026-03-09 - Multi-Source Scanner V4 Implementation

**P0 Fix - Kritischer Scanner-Fehler behoben:**

Der Scanner war vorher blockiert durch DexScreener API Rate-Limiting (HTTP 429 Fehler). 
Jetzt implementiert: **Hochverfügbare Multi-Source Scanner Architektur V4**

**Neue Features:**
- **Exponential Backoff**: Bei HTTP 429 automatisch 1s -> 2s -> 4s -> 8s Verzögerung (max 5 Retries)
- **Request Throttling**: Max 8-10 Requests/Sekunde pro API
- **7 unabhängige Datenquellen**: DexScreener, Birdeye, Jupiter, Raydium, Orca, Meteora, Pump.fun
- **Automatisches Failover**: Wenn eine Quelle blockiert wird, laufen die anderen weiter
- **2-Sekunden Cache**: Reduziert API-Anfragen massiv
- **Health Monitoring**: Echtzeit-Status aller Quellen

**Scanner Performance:**
| Metrik | Vorher | Nachher |
|--------|--------|---------|
| Tokens pro Scan | 0 (blockiert) | 1800-2000 |
| Gesunde Quellen | 0/7 | 7/7 |
| 429 Fehler | Konstant | 0 |
| Scan-Zeit | N/A | ~10s |

**Neue API Endpoints:**
- `GET /api/scanner/health` - Detaillierter Health-Status aller Quellen
- `POST /api/scanner/reset-health` - Health-Status zurücksetzen
- `POST /api/scanner/clear-cache` - Scanner-Cache leeren

**SCANNER HEALTH Log Format:**
```
📊 SCANNER HEALTH
   dexscreener_status: ✅ OK (39 tokens)
   birdeye_status: ✅ OK (39 tokens)
   raydium_status: ✅ OK (411 tokens)
   orca_status: ✅ OK (124 tokens)
   meteora_status: ✅ OK (473 tokens)
   jupiter_status: ✅ OK (800 tokens)
   pumpfun_status: ✅ OK (48 tokens)
   ─────────────────
   tokens_total: 1825
   scan_time: 9.60s
```

### 2026-03-09 - Realtime Launch Sniper Implementation

**Neue Features:**
- **RealtimeLaunchSniper Klasse** - Erkennt neue Token-Launches in < 30 Sekunden
- **Priority-Scoring System** - 0-200 Punkte basierend auf Alter, Liquidität, Aktivität
- **Snipe Queue** - Priorisierte Warteschlange für neue Token-Targets
- **2-Phasen Trade Execution** - Snipe-Targets werden vor normalen Opportunities ausgeführt

---

## Code Architecture

```
/app/backend/
├── server.py           # Haupt-API Server (~7300 Zeilen)
├── scanner/            # NEU: Multi-Source Scanner Modul
│   ├── __init__.py
│   ├── multi_source_scanner.py  # MultiSourceScannerV4
│   ├── rate_limiter.py          # Rate-Limiting & Backoff
│   └── health_monitor.py        # Health Monitoring
├── requirements.txt
└── tests/

/app/frontend/
├── src/
│   ├── App.js
│   ├── components/
│   └── pages/
│       └── Dashboard.jsx
└── package.json
```

---

## Scanner V4 Architecture

### Rate-Limiting Schutz

```python
# Exponential Backoff (1s -> 2s -> 4s -> 8s -> 16s)
if status_code == 429:
    delay = base_delay * (2 ** retry_count)
    await asyncio.sleep(delay)

# Request Throttling (max 8/s pro API)
rate_limiter = RateLimiter(requests_per_second=8.0)
await rate_limiter.acquire(api_name)
```

### Multi-Source Integration

| Quelle | API Endpoint | Typ |
|--------|--------------|-----|
| DexScreener | api.dexscreener.com | Search API |
| Birdeye | public-api.birdeye.so (mit API-Key) | Token List |
| Jupiter | cache.jup.ag/tokens | Verifizierte Tokens |
| Raydium | api.raydium.io/v2/main/pairs | Pool Data |
| Orca | api.mainnet.orca.so/v1/whirlpool/list | Whirlpool Data |
| Meteora | dlmm-api.meteora.ag/pair/all | DLMM Pools |
| Pump.fun | via DexScreener | Bonding Curve |

### Failover System

```
1. API Request fehlgeschlagen?
   ├── Ja → Backoff aktivieren
   │        └── Nach 5 Fehlern: API als unhealthy markieren
   └── Nein → Backoff zurücksetzen

2. API unhealthy?
   ├── Ja → Überspringe diese Quelle
   │        └── Andere Quellen laufen weiter
   └── Nein → Normal scannen
```

---

## API Endpoints

### Scanner V4
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/scanner/stats` | Scanner V4 Statistiken & Health |
| `GET /api/scanner/health` | Detaillierter Health-Status aller Quellen |
| `POST /api/scanner/reset-health` | Health-Status zurücksetzen |
| `POST /api/scanner/clear-cache` | Scanner-Cache leeren |

### Sniper
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/sniper/status` | Sniper-Statistiken & Konfiguration |
| `GET /api/sniper/targets` | Aktuelle Snipe-Targets mit Details |
| `POST /api/sniper/scan` | Manuellen Sniper-Scan triggern |
| `POST /api/sniper/clear` | Queue und Detektionen leeren |

### Auto-Trading
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/auto-trading/status` | Status mit Capital-Metriken |
| `POST /api/auto-trading/start` | Bot starten |
| `POST /api/auto-trading/stop` | Bot stoppen |

---

## Test-Ergebnisse

- **Scanner V4:** 1800+ Tokens pro Scan ✅
- **Alle 7 Quellen:** Gesund und funktionierend ✅
- **Rate-Limiting Schutz:** Aktiv, keine 429 Fehler ✅
- **Backoff System:** Funktioniert korrekt ✅
- **Health Monitoring:** Logs werden generiert ✅
- **Backend API:** Alle Endpoints funktionieren ✅

---

## Credentials

- **PIN:** 1234
- **Birdeye API Key:** Optional (in BIRDEYE_API_KEY env var)

---

## Nächste Schritte (P1)

1. **Refactoring:** server.py in Module aufteilen
2. **Performance Dashboard:** Top profitable Tokens, Profit/Tag
3. **UI für Scanner Health:** Dashboard-Integration

## Zukünftige Features (P2)

1. **MEV Protection:** Sandwich-Attack Schutz
2. **Telegram Notifications**
3. **Jupiter Swap Integration**
