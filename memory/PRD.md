# Pump.fun Trading Bot - PRD v25

## Problem Statement
Automatisiertes Ultra-High-Frequency Trading-System für Pump.fun Tokens auf der Solana Blockchain mit Realtime Launch Sniper und 100+ simultanen Micro-Trades.

## System Status: REALTIME LAUNCH SNIPER + MICRO-TRADE ENGINE AKTIV

Letztes Update: 2026-03-09

---

## Changelog

### 2026-03-09 - Realtime Launch Sniper Implementation

**Neue Features:**
- **RealtimeLaunchSniper Klasse** - Erkennt neue Token-Launches in < 30 Sekunden
- **Priority-Scoring System** - 0-200 Punkte basierend auf Alter, Liquidität, Aktivität
- **Snipe Queue** - Priorisierte Warteschlange für neue Token-Targets
- **2-Phasen Trade Execution** - Snipe-Targets werden vor normalen Opportunities ausgeführt

**Sniper Konfiguration:**
| Parameter | Wert |
|-----------|------|
| ultra_new_seconds | 30s (+100 Punkte) |
| very_new_seconds | 60s (+80 Punkte) |
| new_seconds | 120s (+50 Punkte) |
| min_liquidity_usd | $500 |
| launch_cooldown | 120s |

**Neue API Endpoints:**
- `GET /api/sniper/status` - Sniper-Statistiken
- `GET /api/sniper/targets` - Aktuelle Snipe-Targets
- `POST /api/sniper/scan` - Manueller Sniper-Scan
- `POST /api/sniper/clear` - Queue leeren

### 2026-03-09 - Ultra-High-Frequency Micro-Trade Engine

| Parameter | Wert |
|-----------|------|
| max_parallel_trades | 120 |
| micro_trade_percent | 0.35% |
| max_capital_in_trades | 60% |
| scan_interval | 0.8s |
| take_profit | 8% |
| stop_loss | 6% |
| cooldown | 45s |

---

## Sniper Priority Scoring

```python
# Age-based scoring (0-100 points)
if age < 30s:   score += 100  # 🚨 ULTRA-NEW
elif age < 60s: score += 80   # 🔥 VERY NEW
elif age < 120s: score += 50  # 🆕 NEW
elif age < 300s: score += 25  # ⏰ RECENT

# Liquidity bonus (0-20 points)
if $1k <= liq <= $50k: score += 20  # Good liquidity
elif liq > $50k: score += 10        # High liquidity

# Activity bonus (0-40 points)
score += min(20, buyers * 2)        # Buyer activity
score += min(20, buy_ratio * 5)     # Buy pressure

# Source bonus (0-20 points)
if "pump" in source: score += 20    # Pump.fun launch
elif "raydium": score += 15         # Raydium pool
elif "orca": score += 10            # Orca pool

# Snipe threshold
is_snipe_candidate = score >= 80 AND age < 120s
```

---

## Trading Engine Flow

```
1. SCAN PHASE
   └── Multi-source scanner (7 DEX sources)
   └── Launch sniper processes all tokens
   └── Identify snipe candidates (priority >= 80)

2. SNIPE PHASE (PRIORITY)
   └── Execute snipe targets first
   └── Ultra-new tokens get priority
   └── Max 20 snipe targets per cycle

3. MOMENTUM PHASE
   └── Execute normal opportunities
   └── Sorted by momentum score
   └── Fill remaining trade slots
```

---

## Performance Logs

### LAUNCH SNIPER STATUS
```
==================================================
🎯 LAUNCH SNIPER STATUS
   new_candidates: 3
   queue_size: 5
   total_detections: 42
   avg_detection_age: 45.2s
   top_targets: TOKEN1(185), TOKEN2(142), TOKEN3(98)
==================================================
```

### TRADING ENGINE STATUS
```
==================================================
📊 TRADING ENGINE STATUS
   open_trades: 87
   available_slots: 33
   capital_used: 0.94 SOL (31.3%)
   capital_available: 0.86 SOL
==================================================
```

---

## API Endpoints

### Sniper
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/sniper/status` | Sniper-Statistiken & Konfiguration |
| `GET /api/sniper/targets` | Aktuelle Snipe-Targets mit Details |
| `POST /api/sniper/scan` | Manuellen Sniper-Scan triggern |
| `POST /api/sniper/clear` | Queue und Detektionen leeren |

### Scanner
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/scanner/stats` | Scanner V3 Statistiken |
| `POST /api/scanner/clear-cache` | Cache leeren |

### Auto-Trading
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/auto-trading/status` | Status mit Capital-Metriken |
| `POST /api/auto-trading/start` | Bot starten |
| `POST /api/auto-trading/stop` | Bot stoppen |

---

## Test-Ergebnisse

- **Backend API:** Alle Endpoints funktionieren ✅
- **Scanner V3:** ~1.2s Scan-Zeit ✅
- **Launch Sniper:** Aktiviert, Queue funktioniert ✅
- **Capital Control:** 60% Limit aktiv ✅

---

## Nächste Schritte (P1)

1. **Performance Dashboard** - Top profitable Tokens, Profit/Tag
2. **Refactoring** - server.py in Module aufteilen
3. **UI für Sniper** - Dashboard-Integration

## Zukünftige Features (P2)

1. **MEV Protection** - Sandwich-Attack Schutz
2. **Telegram Notifications**
3. **Jupiter Swap Integration**

---

## Credentials

- **PIN:** 1234

---

## Architektur

```
/app/backend/server.py (~7200 Zeilen)
├── ScannerCache         # 2s TTL Cache
├── MultiSourceScanner   # V3 High-Performance Scanner
├── RealtimeLaunchSniper # NEW: Launch Detection
├── EarlyPumpDetector    # Pump Signal Detection
├── SmartWalletTracker   # Copy-Trading
├── auto_trading_loop    # HFT Trading Engine
└── API Endpoints        # FastAPI Routes
```
