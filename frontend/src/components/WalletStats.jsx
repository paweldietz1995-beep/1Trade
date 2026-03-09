import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { 
  Wallet, 
  TrendingUp, 
  TrendingDown, 
  BarChart3,
  RefreshCw,
  Lock,
  Unlock,
  Layers,
  DollarSign
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Progress } from './ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';

const WalletStats = ({ solPrice = 150, onWalletSelect }) => {
  const { API_URL } = useApp();
  const [walletData, setWalletData] = useState(null);
  const [selectedWallet, setSelectedWallet] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchWalletStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/wallets/status`);
      setWalletData(response.data);
    } catch (err) {
      console.error('Wallet status error:', err);
    } finally {
      setLoading(false);
    }
  }, [API_URL]);

  const refreshBalances = async () => {
    setRefreshing(true);
    try {
      await axios.post(`${API_URL}/wallets/refresh-balances`);
      await fetchWalletStatus();
    } catch (err) {
      console.error('Balance refresh error:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchWalletStatus();
    const interval = setInterval(fetchWalletStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchWalletStatus]);

  useEffect(() => {
    if (onWalletSelect) {
      onWalletSelect(selectedWallet);
    }
  }, [selectedWallet, onWalletSelect]);

  if (loading || !walletData) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]">
        <CardContent className="p-6 flex items-center justify-center">
          <RefreshCw className="w-6 h-6 animate-spin text-neon-cyan" />
          <span className="ml-2 text-muted-foreground">Lade Wallet-Daten...</span>
        </CardContent>
      </Card>
    );
  }

  const { aggregated, wallets, active_tokens, is_initialized, distribution_strategy } = walletData;

  // Keine Multi-Wallet-Konfiguration
  if (!is_initialized || wallets.length === 0) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Wallet className="w-4 h-4 text-muted-foreground" />
            Single-Wallet-Modus
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Multi-Wallet nicht konfiguriert. Erstellen Sie <code>wallets_config.json</code> um mehrere Wallets zu nutzen.
        </CardContent>
      </Card>
    );
  }

  // Aktives Wallet oder Aggregiert
  const displayData = selectedWallet === 'all' 
    ? aggregated 
    : wallets.find(w => w.wallet_id === parseInt(selectedWallet));

  return (
    <div className="space-y-4">
      {/* Header mit Wallet-Auswahl */}
      <Card className="bg-gradient-to-r from-[#0A0A0A] to-[#1a1a2e] border-[#1E293B]">
        <CardContent className="p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <Layers className="w-5 h-5 text-neon-cyan" />
              <span className="font-semibold text-white">Multi-Wallet System</span>
              <Badge variant="outline" className="text-xs">
                {wallets.length} Wallets
              </Badge>
              <Badge variant="outline" className="text-xs text-purple-400 border-purple-400/50">
                {distribution_strategy}
              </Badge>
            </div>
            
            <div className="flex items-center gap-3">
              <Select value={selectedWallet} onValueChange={setSelectedWallet}>
                <SelectTrigger className="w-[180px] bg-[#0A0A0A] border-[#1E293B]">
                  <SelectValue placeholder="Wallet auswählen" />
                </SelectTrigger>
                <SelectContent className="bg-[#0A0A0A] border-[#1E293B]">
                  <SelectItem value="all">Alle Wallets</SelectItem>
                  {wallets.map(w => (
                    <SelectItem key={w.wallet_id} value={w.wallet_id.toString()}>
                      Wallet {w.wallet_id} ({w.balance_sol.toFixed(2)} SOL)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              <button
                onClick={refreshBalances}
                disabled={refreshing}
                className="p-2 rounded-lg bg-[#1E293B] hover:bg-[#2a3a4f] transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Aggregierte Metriken */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <DollarSign className="w-3 h-3" />
              <span>Balance</span>
            </div>
            <div className="text-xl font-bold text-white">
              {displayData?.total_balance_sol?.toFixed(4) || displayData?.balance_sol?.toFixed(4) || '0'} SOL
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              ≈ ${((displayData?.total_balance_sol || displayData?.balance_sol || 0) * solPrice).toFixed(2)}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <BarChart3 className="w-3 h-3" />
              <span>Offene Trades</span>
            </div>
            <div className="text-xl font-bold text-white">
              {displayData?.total_open_trades || displayData?.open_trades_count || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              von max. {displayData?.max_possible_trades || displayData?.max_trades || 120}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <TrendingUp className="w-3 h-3 text-neon-green" />
              <span>P&L</span>
            </div>
            <div className={`text-xl font-bold ${(displayData?.total_pnl_sol || 0) >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
              {(displayData?.total_pnl_sol || 0) >= 0 ? '+' : ''}{(displayData?.total_pnl_sol || 0).toFixed(4)} SOL
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              ≈ ${((displayData?.total_pnl_sol || 0) * solPrice).toFixed(2)}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <Lock className="w-3 h-3 text-yellow-400" />
              <span>Gesperrte Tokens</span>
            </div>
            <div className="text-xl font-bold text-yellow-400">
              {active_tokens || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Doppelkauf-Sperre aktiv
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <TrendingUp className="w-3 h-3" />
              <span>Win Rate</span>
            </div>
            <div className="text-xl font-bold text-white">
              {(displayData?.overall_win_rate || displayData?.win_rate || 0).toFixed(1)}%
            </div>
            <Progress 
              value={displayData?.overall_win_rate || displayData?.win_rate || 0} 
              className="h-1 mt-2"
            />
          </CardContent>
        </Card>
      </div>

      {/* Wallet-Grid (nur wenn "Alle" ausgewählt) */}
      {selectedWallet === 'all' && wallets.length > 1 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {wallets.map(wallet => (
            <Card 
              key={wallet.wallet_id}
              className={`bg-[#0A0A0A] border-[#1E293B] cursor-pointer hover:border-neon-cyan/50 transition-colors ${
                wallet.can_trade ? '' : 'opacity-50'
              }`}
              onClick={() => setSelectedWallet(wallet.wallet_id.toString())}
            >
              <CardContent className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Wallet className="w-4 h-4 text-neon-cyan" />
                    <span className="font-medium text-sm">W{wallet.wallet_id}</span>
                  </div>
                  {wallet.can_trade ? (
                    <Unlock className="w-3 h-3 text-neon-green" />
                  ) : (
                    <Lock className="w-3 h-3 text-neon-red" />
                  )}
                </div>
                
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Balance:</span>
                    <span className="text-white">{wallet.balance_sol.toFixed(3)} SOL</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Trades:</span>
                    <span className="text-white">{wallet.open_trades_count}/{wallet.max_trades}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">P&L:</span>
                    <span className={wallet.total_pnl_sol >= 0 ? 'text-neon-green' : 'text-neon-red'}>
                      {wallet.total_pnl_sol >= 0 ? '+' : ''}{wallet.total_pnl_sol.toFixed(4)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Win:</span>
                    <span className="text-white">{wallet.win_rate.toFixed(0)}%</span>
                  </div>
                </div>
                
                <Progress 
                  value={(wallet.open_trades_count / wallet.max_trades) * 100} 
                  className="h-1 mt-2"
                />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Einzelnes Wallet Details */}
      {selectedWallet !== 'all' && displayData && (
        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Wallet className="w-4 h-4 text-neon-cyan" />
              Wallet {displayData.wallet_id} Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground text-xs mb-1">Public Key</div>
                <div className="font-mono text-xs truncate">{displayData.public_key}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs mb-1">Verfügbares Kapital</div>
                <div className="font-bold text-neon-green">{displayData.available_capital?.toFixed(4)} SOL</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs mb-1">In Trades</div>
                <div className="font-bold text-yellow-400">{displayData.capital_in_trades?.toFixed(4)} SOL</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs mb-1">Gesamte Trades</div>
                <div className="font-bold">{displayData.total_trades} ({displayData.wins}W / {displayData.losses}L)</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default WalletStats;
