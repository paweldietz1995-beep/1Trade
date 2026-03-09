# Pump.fun Trading Bot - PRD v31

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain.
**HIGH-CAPACITY TRADING ENGINE: 50-150 parallele Trades mit massiver Skalierung.**

## System Status: HIGH-CAPACITY TRADING ENGINE AKTIV ✅

Letztes Update: 2026-03-09 16:37

---

## High-Capacity Trading Engine V1

### Erreichte Ziele ✅
| Ziel | Status | Ergebnis |
|------|--------|----------|
| 50-150 parallele Trades | ✅ | 120 aktive Trades erreicht |
| Gelockerte Filter | ✅ | Pass-Rate von 3.4% auf 12.6% |
| Micro-Trade Sizing | ✅ | 0.006 SOL pro Trade |
| Keine Filter-Blockaden | ✅ | skipped_low_amount: 0 |

### Behobene Probleme
1. **Kritischer Bug behoben:** `PortfolioSummary * float` TypeError
2. **Filter-Lockerung:** Momentum-Bedingung von AND auf OR umgestellt
3. **Liquiditäts-Bonus:** Tokens mit $100k+ Liquidität werden automatisch akzeptiert
4. **Settings-Problem:** `max_parallel_trades` von 30 auf 120 erhöht
5. **Min-Trade-Sol:** Von 0.02 auf 0.005 SOL gesenkt
6. **Max-Trades-Per-Token:** Von 1 auf 3 erhöht

### Aktuelle Konfiguration
| Parameter | Wert |
|-----------|------|
| Max offene Trades | 120 |
| Max Trades pro Token | 3 |
| Trade-Größe | 0.006 SOL |
| Min Trade | 0.005 SOL |
| Max Kapital in Trades | 70% |
| Scan-Intervall | 5s |

### Scanner Multi-Source
| Quelle | Tokens/Scan |
|--------|-------------|
| Jupiter | ~800 |
| Meteora | ~479 |
| Raydium | ~411 |
| DexScreener | ~43 |
| Birdeye | ~30 |
| Orca | ~30 |
| PumpFun | ~21 |
| **Gesamt** | **~1814** |

### Momentum Filter (GELOCKERT)
```python
passes_filter = (
    is_momentum OR                    # Hat Momentum-Signal
    signal_score >= 35 OR             # Guter Score
    (is_new_token AND score >= 15) OR # Neuer Token
    (liq >= $10k AND score >= 15) OR  # Etablierter Token
    (liq >= $50k AND score >= 10) OR  # Sehr liquider Token
    (liq >= $100k)                    # Auto-Accept
)
```
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

### Trailing Profit (DYNAMISCH - NEU)
**Dynamischer Trailing-Stop basierend auf Gewinn-Level:**

| Peak P&L | Trail % | Beschreibung |
|----------|---------|--------------|
| +500%+ | 5% | Sehr eng - maximaler Gewinnschutz |
| +200-500% | 8% | Eng |
| +100-200% | 10% | Mittel |
| +50-100% | 12% | Standard |
| +35-50% | 15% | Default |

**MEGA-WINNER Logik:**
- Bei +300%: Automatisch 50% Position sichern
- Schützt gegen plötzliche Einbrüche bei extremen Gewinnen

---

## Aktuelle Performance (2026-03-09)

| Metrik | Wert |
|--------|------|
| Offene Trades | 119 |
| Gesamt P&L | +100.3% |
| Geschlossene Trades | 305 |
| Win Rate | 32% |

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
