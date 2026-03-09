# Pump.fun Trading Bot - PRD v27

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain.
**Optimiert für große Gewinne pro Trade statt viele kleine Micro-Trades.**

## System Status: BIG WINS STRATEGY AKTIV ✅

Letztes Update: 2026-03-09

---

## Changelog

### 2026-03-09 - Big Wins Strategy Implementation

**Komplette Strategieumstellung von "Micro-Trades" auf "Big Wins":**

#### Take-Profit Levels (Mehrstufig)
| Level | Trigger | Aktion |
|-------|---------|--------|
| TP1 | +25% | 30% Position verkaufen |
| TP2 | +60% | weitere 30% verkaufen |
| TP3 | +120% | weitere 20% verkaufen |
| Runner | - | 20% laufen lassen |

#### Trailing Profit System
- **Start:** +35% Gewinn aktiviert Trailing
- **Stop:** 15% unter Peak wird verkauft
- Beispiel: Peak +80% → fällt auf +68% → SELL

#### Minimum Profit Rule
- Kein Verkauf unter **+15%** Gewinn
- Verhindert Micro-Exits bei kleinen Bewegungen

#### Winner Protection
- Bei **+100%** Gewinn: Stop-Loss auf **+40%** setzen
- Schützt große Gewinne automatisch

#### Stop Loss
- Standard: **-15%** (statt -6%)
- Akzeptiert kleine Verluste für große Gewinner

#### Entry Quality Filter (STRIKT)
| Filter | Wert |
|--------|------|
| Liquidität | ≥ $40,000 |
| Market Cap | $80k - $3M |
| Volume Spike | ≥ 2x |
| Token Age | ≤ 12 Stunden |
| Holders | ≥ 50 |

#### Pump Detection
```
volume_1m > volume_5m_average × 1.8
```

#### Slippage Kontrolle
- Max: **8%** (Trade abbrechen)
- Warnung: **5%**

#### Zielwerte
| Metrik | Ziel |
|--------|------|
| Avg Win | +35% bis +80% |
| Avg Loss | -10% bis -15% |
| Win Rate | 30-45% |

---

### 2026-03-09 - Multi-Source Scanner V4

**Hochverfügbare Scanner-Architektur:**
- 7 Datenquellen (DexScreener, Birdeye, Jupiter, Raydium, Orca, Meteora, Pump.fun)
- Exponential Backoff bei Rate-Limiting
- 1800+ Tokens pro Scan
- Automatisches Failover

---

## API Endpoints

### Strategy Endpoints
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/strategy/config` | Big Wins Konfiguration |
| `GET /api/strategy/stats` | Performance-Statistiken |

### Scanner Endpoints
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/scanner/stats` | Scanner V4 Statistiken |
| `GET /api/scanner/health` | Health-Status aller Quellen |
| `POST /api/scanner/reset-health` | Health zurücksetzen |

### Trading Endpoints
| Endpoint | Beschreibung |
|----------|--------------|
| `POST /api/trades/update-all-prices` | Big Wins Preis-Update mit TP Levels |
| `GET /api/auto-trading/status` | Bot-Status |
| `POST /api/auto-trading/start/stop` | Bot starten/stoppen |

---

## Code Architecture

```
/app/backend/
├── server.py           # Haupt-API (Big Wins integriert)
├── scanner/            # Multi-Source Scanner V4
│   ├── multi_source_scanner.py
│   ├── rate_limiter.py
│   └── health_monitor.py
├── trading/            # NEU: Trading Strategie Module
│   ├── __init__.py
│   └── big_wins_strategy.py
└── tests/

/app/frontend/
└── src/
    └── pages/
        └── Dashboard.jsx
```

---

## Credentials

- **PIN:** 1234
- **Birdeye API Key:** Optional (BIRDEYE_API_KEY)

---

## Nächste Schritte

🟠 **P1:** Dashboard UI für Big Wins (TP Levels, Partial Sells anzeigen)
🟠 **P1:** Refactoring server.py in Module
🟡 **P2:** Telegram Benachrichtigungen
🟡 **P2:** MEV Protection
