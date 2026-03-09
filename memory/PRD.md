# Pump.fun Trading Bot - PRD v30

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain.
**Stable Profitability V4: 3-6 Trades/Minute mit Anti-Rug-Schutz.**

## System Status: STABLE PROFITABILITY V4 AKTIV ✅

Letztes Update: 2026-03-09

---

## Stable Profitability V4 Strategie

### Trade-Frequenz Kontrolle
| Parameter | Wert |
|-----------|------|
| Target Min | 3 Trades/Minute |
| Target Max | 6 Trades/Minute |
| Priorisierung | Beste Signale bei Überschuss |

### Dynamische Trade-Skalierung
| Wallet | Trades | Trade-Größe |
|--------|--------|-------------|
| 1 SOL | ~35 | 0.025 SOL |
| 3 SOL | ~80 | 0.035 SOL |
| 10 SOL | ~150 | 0.06 SOL |

### Position Sizing
```
trade_size = wallet_balance / target_active_trades

Beispiel: 3 SOL / 80 = 0.0375 SOL
```

| Parameter | Wert |
|-----------|------|
| Min Trade | 0.02 SOL |
| Max Trade | 0.06 SOL |
| Target | 0.035 SOL |

### Scanner Filter (Grundfilter)
| Filter | Wert |
|--------|------|
| Liquidität | ≥ $30,000 |
| Volume 5m | ≥ $8,000 |
| Holders | ≥ 80 |
| Token Age | 2min - 12h |

### Momentum Entry
| Kriterium | Wert |
|-----------|------|
| Price Change 1m | ≥ 5% |
| Volume Spike | ≥ 2x |
| Buy/Sell Ratio | > 1.2 |
| Upward Trend | Required |

### Anti-Rug Filter (ERWEITERT)
| Filter | Wert |
|--------|------|
| Max Single Wallet | 15% |
| Max Dev Wallet | 10% |
| Min Unique Wallets | 60 |
| Max Top 10 | 60% |

### Scam & Low-Quality Filter
| Filter | Wert |
|--------|------|
| Min Name Length | 3 |
| Random Ticker | Detect |
| Min Liquidity Entry | $25,000 |
| Min Volume 1m | $2,000 |

### Stop-Loss Strategie
| Typ | Wert |
|-----|------|
| Hard Stop | -12% |
| Emergency | -18% |

### Take-Profit Levels
| Level | Trigger | Aktion |
|-------|---------|--------|
| TP1 | +25% | 30% verkaufen |
| TP2 | +60% | 30% verkaufen |
| TP3 | +120% | 20% verkaufen |
| Runner | - | 20% laufen |

### Trailing Profit
- Start: +35%
- Stop: 15% unter Peak

---

## API Endpoints

### Trade Rate
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/trade-rate/stats` | Aktuelle Trade-Rate Statistiken |
| `POST /api/token/check-antirug` | Anti-Rug Check für Token |

### Capital
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/capital/status` | Kapital-Status |
| `GET /api/capital/metrics` | Erweiterte Metriken |

### Strategy
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/strategy/config` | V4 Konfiguration |
| `GET /api/strategy/stats` | Performance Stats |

---

## Zielwerte

| Metrik | Ziel |
|--------|------|
| Aktive Trades | 50-100 |
| Trades/Minute | 3-6 |
| Win Rate | 30-45% |
| Avg Win | +30% bis +80% |
| Avg Loss | -10% bis -12% |

---

## Credentials

- **PIN:** 1234
