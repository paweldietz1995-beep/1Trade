# Pump.fun Trading Bot - PRD v29

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain.
**High Capacity V3: 50-100 gleichzeitige Trades mit dynamischer Positionsgröße.**

## System Status: HIGH CAPACITY V3 AKTIV ✅

Letztes Update: 2026-03-09

---

## High Capacity Scaling V3

### Trade-Kapazität
| Parameter | Wert |
|-----------|------|
| Min Trades | 50 |
| **Max Trades** | **100** |
| Target | 75 |
| Per Token | 1 max |

### Dynamische Trade-Größe
```
trade_size = available_balance / target_active_trades

Beispiel:
Wallet = 3 SOL, Target = 100 Trades
→ Trade-Größe = 0.03 SOL
```

| Parameter | Wert |
|-----------|------|
| Min Trade | 0.02 SOL |
| Max Trade | 0.08 SOL |
| Target | 0.03 SOL |

### Kapital-Management
| Parameter | Wert |
|-----------|------|
| Max in Trades | **80%** |
| Reserve | 20% |
| Warn Level | 10% |

### API Endpoints (NEU)
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/capital/status` | Kapital-Status & Trade-Kapazität |
| `GET /api/capital/metrics` | Erweiterte Metriken |
| `GET /api/strategy/config` | High Capacity V3 Config |

---

## Big Wins Strategie

### Take-Profit Levels
| Level | Trigger | Aktion |
|-------|---------|--------|
| TP1 | +25% | 30% verkaufen |
| TP2 | +60% | 30% verkaufen |
| TP3 | +120% | 20% verkaufen |
| Runner | - | 20% laufen |

### Stop-Loss
- **Hard Stop:** -12%
- **Max Loss:** -15%

### Entry Quality
| Filter | Wert |
|--------|------|
| Liquidity | ≥ $25,000 |
| Volume 5m | ≥ $5,000 |
| Holders | ≥ 60 |
| Token Age | 90s - 12h |
| Price Change | ≥ 4% |

---

## Skalierung

### Mit 3 SOL Wallet
```
3 SOL × 80% = 2.4 SOL verfügbar
2.4 SOL / 0.03 SOL = ~80 Trades möglich
```

### Auto-Scaling
- Mehr Kapital → Mehr oder größere Trades
- Weniger Kapital → Kleinere Trades
- Dynamische Anpassung pro Scan

---

## Credentials

- **PIN:** 1234

---

## Nächste Schritte

🟠 **P1:** Dashboard UI für Kapital-Metriken
🟡 **P2:** Telegram Benachrichtigungen
