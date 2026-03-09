# Pump.fun Trading Bot - PRD v28

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain.
**Big Wins V2: Große Gewinne, kleine Verluste.**

## System Status: BIG WINS V2 AKTIV ✅

Letztes Update: 2026-03-09

---

## Big Wins V2 Strategy

### Ziel
- **Winrate:** 30-45%
- **Avg Win:** +30% bis +80%
- **Avg Loss:** -10% bis -12%

### Stop-Loss (HARD LIMIT)
| Typ | Wert |
|-----|------|
| Hard Stop | **-12%** |
| Max Loss | **-15%** (Emergency) |

Der Bot verkauft **automatisch** bei -12% Verlust.
Verluste über -15% sind **unmöglich**.

### Take-Profit Levels
| Level | Trigger | Aktion |
|-------|---------|--------|
| TP1 | +25% | 30% verkaufen |
| TP2 | +60% | 30% verkaufen |
| TP3 | +120% | 20% verkaufen |
| Runner | - | 20% laufen lassen |

### Trailing Profit
- **Start:** +35%
- **Stop:** 15% unter Peak

### Entry Quality Filter (VERSCHÄRFT)
| Filter | Wert |
|--------|------|
| Liquidität | ≥ $30,000 |
| Volume 5m | ≥ $8,000 |
| Holders | ≥ 80 |
| Token Age | 2min - 12h |
| Market Cap | $50k - $3M |

### Momentum Entry
| Kriterium | Wert |
|-----------|------|
| Price Change 1m | ≥ 5% |
| Volume Spike | ≥ 2x |
| Buyers 1m | > Sellers |

### Position Sizing
| Parameter | Wert |
|-----------|------|
| Trade Size | 2.5% Wallet |
| Max Trade | 0.1 SOL |
| Max Trades | 25 parallel |
| Per Token | 1 Trade max |
| Capital in Trades | 50% max |

### Risk Management
| Parameter | Wert |
|-----------|------|
| Daily Loss Limit | 15% |
| Max Loss Streak | 5 |
| Pause nach Streak | 5 Minuten |

---

## API Endpoints

### Strategy
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/strategy/config` | Big Wins V2 Konfiguration |
| `GET /api/strategy/stats` | Performance-Statistiken |

### Scanner
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/scanner/health` | Scanner Health Status |
| `POST /api/scanner/reset-health` | Health zurücksetzen |

---

## Changelog

### 2026-03-09 - Big Wins V2

**Verlust-Begrenzung:**
- Hard Stop Loss: -12% (statt -15%)
- Emergency Stop: -15% (absolutes Maximum)
- Keine Trades über -15% Verlust möglich

**Entry-Filter verschärft:**
- Liquidity: $30k (statt $40k variabel)
- Volume 5m: $8k (neu)
- Holders: 80 (statt 50)
- Token Age: min 2 Minuten (statt 30s)
- Price Change: 5% (statt 3%)

**Risk Management:**
- Max Loss Streak: 5 (statt 8)
- Daily Loss: 15% (statt 20%)
- Max Trades per Token: 1 (statt 2)

---

## Credentials

- **PIN:** 1234
- **Birdeye API Key:** Optional (BIRDEYE_API_KEY)
