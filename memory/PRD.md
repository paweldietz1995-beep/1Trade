# Pump.fun Trading Bot - PRD v40

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain.
**MULTI-WALLET HIGH-CAPACITY ENGINE: Bis zu 1200 parallele Trades (10 Wallets x 120 Trades)**

## System Status: BOT AKTIVIERT & HANDELT! ✅

Letztes Update: 2026-03-10 16:05

---

## P0 FIX: Wallet-Backend-Synchronisation (v1.4.1)

### Problem gelöst
Nach dem Refactoring der Frontend-Wallet-Logik (von `wallet-adapter` zu eigenem `PhantomWalletProvider`) wurde das Backend nicht mehr über Wallet-Verbindungen informiert. Dies führte dazu, dass:
- System-Diagnose zeigte "Wallet: Disconnected" obwohl das Frontend "Connected" zeigte
- Trading Engine startete nicht automatisch nach Wallet-Verbindung
- Live-Trades wurden nicht ausgeführt

### Lösung
1. **Frontend `PhantomWalletContext.jsx`:** Nach erfolgreicher Phantom-Verbindung wird automatisch `/api/wallet/sync` mit JSON-Body aufgerufen
2. **Automatischer Engine-Start:** Nach erfolgreichem Sync prüft das Frontend `/api/wallet/can-trade` und startet die Trading Engine via `/api/auto-trading/start`
3. **Dashboard aktualisiert:** Nutzt jetzt `isWalletConnected` (Kombination aus PhantomWallet und WalletAdapter Status)
4. **UI-Feedback:** WalletConnect-Komponente zeigt Backend-Sync-Status und Trading-Engine-Status
5. **Backend unterstützt beide Formate:** JSON-Body und Query-Parameter für Rückwärtskompatibilität

### Code-Änderungen (Frontend)
```javascript
// PhantomWalletContext.jsx - Sync nach Verbindung mit JSON Body
const syncWithBackend = useCallback(async (address) => {
  const response = await fetch(`${API_URL}/api/wallet/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ wallet: address, force: true })
  });
  // Auto-Start Trading Engine
  await autoStartTradingEngine();
});
```

### Code-Änderungen (Backend)
```python
# server.py - Unterstützt JSON Body und Query Params
class WalletSyncRequest(BaseModel):
    wallet: str
    force: bool = False

@api_router.post("/wallet/sync")
async def sync_wallet(request: Optional[WalletSyncRequest] = None, address: str = None, force: bool = False):
    wallet_address = request.wallet if request else address
    # ... sync logic
```

### Verifizierung
```bash
# JSON Body Sync (neu)
curl -X POST "/api/wallet/sync" -H "Content-Type: application/json" -d '{"wallet": "<ADDRESS>"}'
# Erwartetes Ergebnis: {"success": true, "status": "synced"}

# Query Param Sync (backward compat)
curl -X POST "/api/wallet/sync?address=<ADDRESS>&force=true"
# Erwartetes Ergebnis: {"success": true, "status": "synced"}

# Can Trade Check
curl "/api/wallet/can-trade"
# Erwartetes Ergebnis: {"can_start": true, "wallet_synced": true}
```

### Neue Features
- **Backend-Sync-Status:** WalletConnect zeigt "Backend: Synchronisiert/Nicht verbunden"
- **Engine-Status:** WalletConnect zeigt "Engine: Aktiv/Inaktiv"
- **Toast-Benachrichtigungen:** Feedback bei Verbindung, Sync und Engine-Start

---

## KRITISCHE FIXES (v1.3) - Bot handelt wieder!

### Probleme gelöst:
1. **"Maximum parallel trades reached" Fehler** - `create_trade` Funktion hatte `settings.max_parallel_trades` (aus DB) statt `ENGINE_CONFIG["max_open_trades"]`
2. **Trade-Größe zu klein** - `min_trade_sol: 0.02` blockierte Trades mit 0.008 SOL
3. **Hardcodierte Werte** - Momentum-Score Filter war auf 70 statt Config-Wert

### Code-Änderungen:
```python
# FIX 1: create_trade Limit-Prüfung
max_parallel = ENGINE_CONFIG.get("max_open_trades", 120)
if open_trades >= max_parallel:
    raise HTTPException(...)

# FIX 2: Min-Trade auf Mikro-Level
"min_micro_trade_sol": 0.002  # Statt 0.02

# FIX 3: available_slots Berechnung
max_parallel = ENGINE_CONFIG["max_open_trades"]  # Statt min(settings, ENGINE_CONFIG)
```

### Ergebnis:
- **59 neue Trades in wenigen Minuten!**
- `open_trades: 75` (von vorher 23)
- Bot läuft stabil und scannt kontinuierlich

---

## Take All Profit Button (v1.2)

### Features
- **Take All Profit**: Schließt alle Trades mit Gewinn auf Knopfdruck
- **Close All**: Notfall-Funktion zum Schließen aller Trades
- **Detaillierte Statistiken**: Zeigt geschlossene Trades und Gesamtgewinn

### Neue API Endpoints
| Endpoint | Beschreibung |
|----------|--------------|
| `POST /api/trades/take-profit-all` | Alle profitablen Trades schließen |
| `POST /api/trades/close-all` | ALLE Trades schließen (Notfall) |

### Frontend
- Zwei neue Buttons im LiveTradesPanel
- Bestätigungsdialog vor Ausführung
- Echtzeit-Feedback mit Toast-Benachrichtigungen

---

## NEU: Verbessertes Wallet-Logging (v1.2)

### Features
- **Detailliertes Logging** bei Wallet-Auswahl
- Zeigt Status jedes Wallets: Balance, offene Trades, Loss-Streak
- Erklärt warum ein Wallet ausgewählt/übersprungen wurde
- Hilft bei Diagnose wenn Wallets nicht handeln

### Strategie geändert
- Von `free_capital` auf `round_robin` geändert
- Damit handeln alle Wallets gleichmäßig, nicht nur das mit dem meisten Kapital

---

## Pro-Wallet Loss-Streak Management (v1.1)

### Problem gelöst
Der Bot pausierte global wegen "Loss streak limit reached" auf einem Wallet, was **alle** Wallets am Handeln hinderte.

### Lösung
- **Loss-Streak-Zähler pro Wallet** statt global
- **Einzelne Wallets** werden bei zu vielen Verlusten pausiert, **nicht** der ganze Bot
- **Andere Wallets** können weiter handeln
- **Reset-Funktionen** für einzelne oder alle Wallets

### Neue Attribute (WalletState)
```python
consecutive_losses: int = 0  # Zähler pro Wallet
```

### Neue API Endpoints
| Endpoint | Beschreibung |
|----------|--------------|
| `POST /api/trading/reset-loss-streak` | Reset für ALLE Wallets |
| `POST /api/trading/reset-wallet-loss-streak/{wallet_id}` | Reset für EIN Wallet |

### Konfiguration (wallets_config.json)
```json
{
  "distribution_strategy": "free_capital",
  "max_trades_per_wallet": 120,
  "loss_streak_limit": 50,  // NEU
  "wallets": ["privkey1...", "privkey2...", ...]
}
```

### Aggregierte Stats erweitert
- `tradeable_wallets`: Anzahl der Wallets, die handeln können
- `wallets_at_loss_limit`: Anzahl der pausierten Wallets
- `loss_streak_limit`: Konfiguriertes Limit

---

## Multi-Wallet System (10 Wallets)

### Features
- **10 unabhängige Wallets** mit eigenen Balances
- **Zentrale Handelslogik** - ein Bot-Prozess für alle Wallets
- **Verteilung nach freiem Kapital** (konfigurierbar: round_robin, least_trades)
- **Strikte Doppelkauf-Sperre** - ein Token wird nur von einem Wallet gehandelt
- **1200 parallele Trades möglich** (10 x 120)
- **Dashboard mit Wallet-Filter** - Einzelne oder alle Wallets anzeigen

### Neue Dateien
- `/app/backend/multi_wallet.py` - MultiWalletManager Klasse
- `/app/backend/wallets_config.json` - Wallet-Konfiguration (10 Keys)
- `/app/backend/wallets_config.example.json` - Beispiel-Konfiguration
- `/app/frontend/src/components/WalletStats.jsx` - Dashboard-Komponente

### API Endpoints
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/wallets/status` | Status aller Wallets |
| `GET /api/wallets/{id}` | Einzelnes Wallet |
| `POST /api/wallets/refresh-balances` | Balance-Update |
| `PUT /api/wallets/strategy` | Strategie ändern |
| `GET /api/wallets/trades/{id}` | Trades pro Wallet |

### Konfiguration (wallets_config.json)
```json
{
  "distribution_strategy": "free_capital",
  "max_trades_per_wallet": 120,
  "wallets": ["privkey1...", "privkey2...", ...]
}
```

### Trade-Modell erweitert
```python
class Trade:
    wallet_id: int = 0  # NEU: Index des Wallets (0-9)
```

### Dashboard WalletStats-Komponente
- Dropdown zur Wallet-Auswahl (Alle / Einzeln)
- Aggregierte Statistiken für alle Wallets
- Pro-Wallet: Balance, P&L, Win Rate, offene Trades
- Gesperrte Tokens anzeigen (Doppelkauf-Sperre)

---

## 2-Sekunden Preis-Monitor

### Features
- **Dedizierter Background-Task** (`fast_price_monitor()`)
- **Batch-Preisabfragen** via DexScreener (Birdeye als Option)
- **Unabhängig vom Scanner** - reagiert schneller auf Kursbewegungen
- **Coverage: 93/56 (166%)** - Pair- und Token-Adressen

### Implementierung
```python
async def fast_price_monitor():
    while True:
        result = await update_all_trade_prices()
        await asyncio.sleep(2.0)  # 2-Sekunden-Intervall
```

---

## NEU: Mehrstufige Gewinnsicherung (ULTRA-WINNER)

### Exit-Strategie V2
| Stufe | Trigger | Aktion | Trail |
|-------|---------|--------|-------|
| MEGA_500 | +500% | 30% sichern | 8% |
| ULTRA_1000 | +1000% | 30% sichern | 5% |
| ULTRA_2000 | +2000% | 20% sichern | 5% |
| Runner | Rest | Mit Trail laufen | 5% |

### Dynamischer Trailing-Stop
| Peak P&L | Trail % |
|----------|---------|
| +1000%+ | 5% |
| +500-1000% | 8% |
| +200-500% | 10% |
| +100-200% | 12% |
| +35-100% | 15% |

---

## NEU: Performance Dashboard

### Komponenten
- `/app/frontend/src/components/PerformanceStats.jsx`
- `/app/backend/dashboard.py` (Streamlit-Version für lokale Nutzung)

### API Endpoints
- `GET /api/dashboard/snapshot` - Aggregierte Metriken

### Angezeigte Metriken
- Win Rate & P&L
- Ausstiegsgründe (Bar Chart)
- Top Gewinner (Live)
- MEGA/ULTRA Exit Counter
- Scanner Status

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
