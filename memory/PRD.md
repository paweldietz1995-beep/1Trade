# Pump.fun Trading Bot - PRD v11

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain mit vollständiger deutscher Benutzeroberfläche.

## Vollständig Implementiert ✅

### 1. High-Capacity Trading Engine ✅
**Optimiert für Scalping-Strategie (März 2026)**
- **Scan-Intervall:** 2 Sekunden
- **Max Tokens pro Scan:** 200
- **Max offene Trades:** 20
- **Max Trades pro Token:** 1 (Duplikat-Schutz)
- **Signal Cooldown:** 60 Sekunden pro Token
- **Min Signal Score:** 45

**Scalping-Parameter:**
- Take Profit: 10% (8-12%)
- Stop Loss: 6% (5-7%)
- Trailing Stop: 5% (aktiviert nach 6% Profit)
- Tagesverlust-Limit: 15%
- Verlust-Streak-Limit: 5

### 2. Echtzeit-Preisverfolgung ✅ (März 2026)
**Neuer Endpoint:** `POST /api/trades/update-all-prices`
- Bulk-Preisaktualisierung für alle offenen Trades
- Update-Intervall: 3 Sekunden
- Automatische TP/SL/Trailing-Stop-Prüfung
- Auto-Close bei Limit-Erreichung

### 3. Token Scanner Stabilität ✅ (März 2026)
**Verbesserte API-Aufrufe mit Rate-Limiting:**
- Token-Cache (15 Sekunden TTL)
- Relaxierte Filter: Liq ≥ $3k ODER Vol ≥ $5k
- Diverse Quellen: pump.fun, meme, degen
- 24+ Tokens pro Scan

### 4. Duplikat-Trade-Schutz ✅
- Max 1 Trade pro Token
- Signal-Cooldown nach Trade-Ausführung
- Automatische Überspringung bei existierenden Trades

### 5. Kapitalmanagement ✅
- Dynamische Trade-Größe: `walletBalance / maxOpenTrades`
- Beispiel: 3 SOL / 20 = 0.15 SOL pro Trade
- Liquiditätsprüfung vor Ausführung

### 6. Geschlossene Trades Historie ✅
**Backend:** `GET /api/trades?status=CLOSED`
**Frontend:** `LiveTradesPanel.jsx`
- Tabelle mit P&L-Farbcodierung
- Statistik-Zusammenfassung
- Trade-Detail-Modal

### 7. Trade-Schließ-System ✅
**Endpoint:** `POST /api/trades/{trade_id}/close`
- Paper Mode: Simulierte Schließung
- Live Mode: Jupiter-Swap (vorbereitet)
- Automatische Preisabfrage

### 8. Deutsche Benutzeroberfläche ✅

| Feature | Deutsch |
|---------|---------|
| Scanner | Token Scanner |
| Live P&L | Live P&L |
| Active Trades | Aktive Trades |
| Closed Trades | Geschlossene Trades |
| Win Rate | Trefferquote |
| Signal | SIGNAL |
| Risk | RISK |
| Trade | Trade |

## API Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/tokens/scan` | GET | Token-Scanner mit Caching |
| `/api/trades?status=OPEN` | GET | Offene Trades |
| `/api/trades?status=CLOSED` | GET | Geschlossene Trades |
| `/api/trades/{id}/close` | POST | Trade schließen |
| `/api/trades/update-all-prices` | POST | Bulk-Preisaktualisierung |
| `/api/portfolio` | GET | Portfolio-Statistiken |
| `/api/auto-trading/start` | POST | Engine starten |
| `/api/auto-trading/stop` | POST | Engine stoppen |

## Nächste Schritte (Phase 2)

1. **Jupiter Swap Integration** (P1)
   - Live Mode Swap-Ausführung

2. **Performance Dashboard** (P1)
   - Top profitable Tokens
   - Profit per Hour/Day

3. **Liquiditäts-Migration Detektor** (P1)
   - Pump.fun → Raydium/Orca

## Backlog (Phase 3)

- Ultra-Fast Sniper Modul
- MEV-Schutz
- Telegram Benachrichtigungen

## Credentials
- **PIN:** 1234 (anpassbar)
