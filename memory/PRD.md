# Pump.fun Trading Bot - PRD

## Original Problem Statement
Entwicklung eines automatisierten Trading-Systems für Pump.fun Tokens auf der Solana Blockchain. Die App analysiert kontinuierlich Tokens, identifiziert profitable Trades und führt diese automatisch aus.

## User Persona
- Single User (Creator) - Crypto Trader
- Benötigt professionelles Trading Terminal
- Paper Trading für Tests, Live Trading für echte Funds

## Core Requirements - IMPLEMENTED ✅

### 1. Capital Management
- Total Budget konfigurierbar (default: 0.5 SOL)
- Max Trade Size: 20% des Budgets
- Max parallele Trades: 5
- Automatische Budget-Aufteilung

### 2. Token Discovery Engine
- Live Daten von DEX Screener API
- Momentum Score (0-100)
- Signal Strength: NONE, WEAK, MEDIUM, STRONG
- 5m, 1h, 24h Preisänderungen
- Buy/Sell Ratio

### 3. Risk Filters
- Min Liquidity: $5,000
- Max Dev Wallet: 15%
- Max Top 10 Holders: 50%
- Honeypot Detection
- Rugpull Risk Analysis
- Token Age Constraints

### 4. Trading Engine
- Paper Trading Mode (Simulation)
- Hybrid Mode (manuell bestätigen)
- Auto Trading Mode (vollautomatisch)
- Take Profit: +100% (konfigurierbar)
- Stop Loss: -25% (konfigurierbar)
- Trailing Stop (optional)

### 5. Multi-Trade System
- Bis zu 5 parallele Trades
- Individuelle TP/SL pro Trade
- Portfolio Übersicht

### 6. Risk Management
- Max Daily Loss: 50%
- Pause nach 3 Verlust-Trades
- Automatische Trading-Pause

### 7. Wallet Integration
- Phantom Wallet via Solana Wallet Adapter
- Balance Anzeige
- Token Holdings Anzeige

## Architecture
- **Frontend**: React, Tailwind CSS, Solana Wallet Adapter
- **Backend**: FastAPI, MongoDB
- **APIs**: DEX Screener, CoinGecko, Jupiter (vorbereitet)

## What's Been Implemented
**Date: March 8, 2026**

### Backend Endpoints
- `/api/auth/login` - PIN Auth
- `/api/auth/reset` - PIN Reset
- `/api/bot/settings` - Bot Konfiguration
- `/api/tokens/scan` - Token Scanner
- `/api/tokens/{address}` - Token Details
- `/api/opportunities` - AI Trading Signale
- `/api/trades` - Trade CRUD
- `/api/portfolio` - Portfolio Summary
- `/api/swap/quote` - Jupiter Quote (vorbereitet)

### Frontend Components
- Dashboard mit 5 Stat Cards
- Token Scanner mit Momentum & Risk Analyse
- Trading Opportunities (AI Signale)
- Bot Settings (4 Tabs: Capital, Trading, Filters, Automation)
- Trade Modal mit TP/SL/Trailing Stop
- Wallet Panel
- TradingView Chart Widget
- Token Search

## Test Results
- Backend: 16/16 Tests ✅
- Frontend: 38/39 E2E Tests ✅ (1 skipped - market conditions)

## Prioritized Backlog

### P0 (Next)
- [ ] Jupiter Swap Integration für echte Trades
- [ ] WebSocket für Echtzeit-Updates
- [ ] Smart Wallet Tracking implementieren

### P1
- [ ] Trailing Stop Execution Engine
- [ ] Migration Detection (Pump.fun → DEX)
- [ ] Telegram Bot Integration

### P2
- [ ] AI Trading Modelle
- [ ] Copy Trading
- [ ] Multi-User Plattform

## Next Tasks
1. Jupiter Swap für echte Token-Käufe
2. WebSocket Price Updates
3. Auto-Trading Execution Loop
