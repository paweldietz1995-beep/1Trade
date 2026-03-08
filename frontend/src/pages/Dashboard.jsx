import React, { useState, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { LAMPORTS_PER_SOL } from '@solana/web3.js';
import axios from 'axios';
import { 
  Wallet, 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  Zap, 
  Shield, 
  Target,
  BarChart3,
  RefreshCw,
  Settings,
  LogOut,
  AlertTriangle,
  Search,
  Bot,
  Pause,
  Play,
  DollarSign,
  Layers,
  Eye,
  Radio
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import TokenScanner from '../components/TokenScanner';
import ActiveTrades from '../components/ActiveTrades';
import TradingOpportunities from '../components/TradingOpportunities';
import BotSettingsPanel from '../components/BotSettingsPanel';
import WalletPanel from '../components/WalletPanel';
import TokenSearch from '../components/TokenSearch';
import TradingViewWidget from '../components/TradingViewWidget';

const Dashboard = () => {
  const { logout, API_URL } = useApp();
  const { connected, publicKey } = useWallet();
  const { connection } = useConnection();
  
  const [walletBalance, setWalletBalance] = useState(0);
  const [solPrice, setSolPrice] = useState(150);
  const [portfolio, setPortfolio] = useState(null);
  const [botSettings, setBotSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [showSettings, setShowSettings] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [selectedToken, setSelectedToken] = useState(null);
  const [autoTrading, setAutoTrading] = useState(false);

  // Fetch wallet balance
  const fetchWalletBalance = useCallback(async () => {
    if (connected && publicKey && connection) {
      try {
        const balance = await connection.getBalance(publicKey);
        setWalletBalance(balance / LAMPORTS_PER_SOL);
      } catch (error) {
        console.error('Error fetching balance:', error);
      }
    }
  }, [connected, publicKey, connection]);

  // Fetch portfolio and settings
  const fetchData = useCallback(async () => {
    try {
      const [portfolioRes, settingsRes, priceRes] = await Promise.all([
        axios.get(`${API_URL}/portfolio`),
        axios.get(`${API_URL}/bot/settings`),
        axios.get(`${API_URL}/market/sol-price`)
      ]);
      setPortfolio(portfolioRes.data);
      setBotSettings(settingsRes.data);
      setSolPrice(priceRes.data.price);
      setAutoTrading(settingsRes.data.auto_trade_enabled);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
    setLoading(false);
  }, [API_URL]);

  useEffect(() => {
    fetchWalletBalance();
    fetchData();
    
    const interval = setInterval(() => {
      fetchWalletBalance();
      fetchData();
    }, 15000);
    
    return () => clearInterval(interval);
  }, [fetchWalletBalance, fetchData]);

  const toggleAutoTrading = async () => {
    if (!botSettings) return;
    
    try {
      const newSettings = { ...botSettings, auto_trade_enabled: !autoTrading };
      await axios.put(`${API_URL}/bot/settings`, newSettings);
      setAutoTrading(!autoTrading);
      setBotSettings(newSettings);
    } catch (error) {
      console.error('Error toggling auto trading:', error);
    }
  };

  const handleTokenSelect = (token) => {
    setSelectedToken(token);
    setActiveTab('chart');
  };

  const formatUSD = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const formatSOL = (value) => {
    return `${value?.toFixed(4) || '0.0000'} SOL`;
  };

  return (
    <div className="min-h-screen" data-testid="dashboard">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-[#1E293B] bg-[#050505]/95 backdrop-blur-sm">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Zap className="w-6 h-6 text-neon-cyan" />
              <span className="text-xl font-heading font-bold tracking-tight">PUMP TERMINAL</span>
            </div>
            
            {/* Auto Trading Toggle */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-sm border ${
              autoTrading 
                ? 'bg-neon-green/10 border-neon-green/30' 
                : 'bg-[#0A0A0A] border-[#1E293B]'
            }`}>
              <Bot className={`w-4 h-4 ${autoTrading ? 'text-neon-green animate-pulse' : 'text-muted-foreground'}`} />
              <span className={`text-xs uppercase tracking-wider ${autoTrading ? 'text-neon-green' : 'text-muted-foreground'}`}>
                {autoTrading ? 'Auto Trading ON' : 'Auto Trading OFF'}
              </span>
              <Switch 
                checked={autoTrading} 
                onCheckedChange={toggleAutoTrading}
                data-testid="auto-trading-toggle"
              />
            </div>

            {/* Paper Mode Indicator */}
            {botSettings?.paper_mode && (
              <Badge className="bg-neon-cyan/20 text-neon-cyan border-none">
                <Shield className="w-3 h-3 mr-1" />
                Paper Mode
              </Badge>
            )}

            {/* Pause Warning */}
            {portfolio?.is_paused && (
              <Badge className="bg-neon-red/20 text-neon-red border-none animate-pulse">
                <Pause className="w-3 h-3 mr-1" />
                Trading Paused
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Search */}
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => setShowSearch(true)}
              className="border-[#1E293B]"
              data-testid="search-button"
            >
              <Search className="w-4 h-4 mr-2" />
              Search Token
            </Button>

            {/* SOL Price */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0A0A0A] border border-[#1E293B] rounded-sm">
              <span className="text-xs text-muted-foreground">SOL</span>
              <span className="font-mono text-sm text-neon-green">{formatUSD(solPrice)}</span>
            </div>

            {/* Wallet */}
            <WalletMultiButton />

            {/* Settings */}
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => setShowSettings(true)}
              data-testid="settings-button"
            >
              <Settings className="w-5 h-5" />
            </Button>

            {/* Logout */}
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={logout}
              data-testid="logout-button"
            >
              <LogOut className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-4">
        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
          {/* Wallet Balance */}
          <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="wallet-balance-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Wallet</span>
                <Wallet className="w-4 h-4 text-neon-cyan" />
              </div>
              <div className="font-mono text-xl font-bold text-neon-cyan">
                {connected ? formatSOL(walletBalance) : '--'}
              </div>
              <div className="text-xs text-muted-foreground">
                {connected ? formatUSD(walletBalance * solPrice) : 'Connect wallet'}
              </div>
            </CardContent>
          </Card>

          {/* Available Budget */}
          <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="budget-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Available</span>
                <DollarSign className="w-4 h-4 text-neon-green" />
              </div>
              <div className="font-mono text-xl font-bold text-neon-green">
                {portfolio ? formatSOL(portfolio.available_sol) : '--'}
              </div>
              <div className="text-xs text-muted-foreground">
                of {botSettings ? formatSOL(botSettings.total_budget_sol) : '--'} budget
              </div>
            </CardContent>
          </Card>

          {/* In Trades */}
          <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="in-trades-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">In Trades</span>
                <Layers className="w-4 h-4 text-neon-violet" />
              </div>
              <div className="font-mono text-xl font-bold">
                {portfolio ? formatSOL(portfolio.in_trades_sol) : '--'}
              </div>
              <div className="text-xs text-muted-foreground">
                {portfolio?.open_trades || 0} active positions
              </div>
            </CardContent>
          </Card>

          {/* Total P&L */}
          <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="total-pnl-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Total P&L</span>
                {portfolio && portfolio.total_pnl >= 0 ? (
                  <TrendingUp className="w-4 h-4 text-neon-green" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-neon-red" />
                )}
              </div>
              <div className={`font-mono text-xl font-bold ${portfolio && portfolio.total_pnl >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                {portfolio ? `${portfolio.total_pnl >= 0 ? '+' : ''}${portfolio.total_pnl_percent.toFixed(1)}%` : '--'}
              </div>
              <div className={`text-xs ${portfolio && portfolio.total_pnl >= 0 ? 'text-neon-green/70' : 'text-neon-red/70'}`}>
                {portfolio ? `${portfolio.total_pnl >= 0 ? '+' : ''}${formatSOL(portfolio.total_pnl)}` : '--'}
              </div>
            </CardContent>
          </Card>

          {/* Win Rate */}
          <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="win-rate-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Win Rate</span>
                <Target className="w-4 h-4 text-neon-green" />
              </div>
              <div className="font-mono text-xl font-bold">
                {portfolio ? `${portfolio.win_rate.toFixed(0)}%` : '--'}
              </div>
              <div className="text-xs text-muted-foreground">
                {portfolio ? `${portfolio.closed_trades} trades closed` : '--'}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Pause Warning Banner */}
        {portfolio?.is_paused && (
          <div className="mb-4 p-4 bg-neon-red/10 border border-neon-red/30 rounded-sm flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-neon-red" />
              <div>
                <div className="font-semibold text-neon-red">Trading Paused</div>
                <div className="text-sm text-muted-foreground">{portfolio.pause_reason}</div>
              </div>
            </div>
            <Button 
              variant="outline" 
              className="border-neon-red/30 text-neon-red hover:bg-neon-red/10"
              onClick={() => setShowSettings(true)}
            >
              <Settings className="w-4 h-4 mr-2" />
              Adjust Settings
            </Button>
          </div>
        )}

        {/* Main Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="bg-[#0A0A0A] border border-[#1E293B]">
            <TabsTrigger value="overview" data-testid="tab-overview">
              <Activity className="w-4 h-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="scanner" data-testid="tab-scanner">
              <Radio className="w-4 h-4 mr-2" />
              Scanner
            </TabsTrigger>
            <TabsTrigger value="trades" data-testid="tab-trades">
              <BarChart3 className="w-4 h-4 mr-2" />
              Trades
            </TabsTrigger>
            <TabsTrigger value="chart" data-testid="tab-chart">
              <Eye className="w-4 h-4 mr-2" />
              Chart
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Trading Opportunities - 2 columns */}
              <div className="lg:col-span-2">
                <TradingOpportunities onSelectToken={handleTokenSelect} />
              </div>
              
              {/* Wallet Panel */}
              <div className="space-y-4">
                <WalletPanel />
                <ActiveTrades compact />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="scanner">
            <TokenScanner onSelectToken={handleTokenSelect} />
          </TabsContent>

          <TabsContent value="trades">
            <ActiveTrades />
          </TabsContent>

          <TabsContent value="chart">
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              {/* Chart - 3 columns */}
              <div className="lg:col-span-3">
                <Card className="bg-[#0A0A0A] border-[#1E293B] h-[600px]">
                  <CardHeader className="border-b border-[#1E293B] py-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="font-heading text-base flex items-center gap-2">
                        <Eye className="w-5 h-5 text-neon-cyan" />
                        {selectedToken ? `${selectedToken.symbol} / USD` : 'SOL / USD'}
                      </CardTitle>
                      {selectedToken && (
                        <div className="flex items-center gap-4 text-sm">
                          <span className="font-mono">${selectedToken.price_usd?.toFixed(6)}</span>
                          <span className={selectedToken.price_change_24h >= 0 ? 'text-neon-green' : 'text-neon-red'}>
                            {selectedToken.price_change_24h >= 0 ? '+' : ''}{selectedToken.price_change_24h?.toFixed(1)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="p-0 h-[540px]">
                    <TradingViewWidget 
                      symbol={selectedToken ? `RAYDIUM:${selectedToken.symbol}USD` : 'COINBASE:SOLUSD'} 
                    />
                  </CardContent>
                </Card>
              </div>

              {/* Trade Panel - 1 column */}
              <div>
                <ActiveTrades compact />
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <BotSettingsPanel 
          settings={botSettings}
          onClose={() => setShowSettings(false)} 
          onSave={(newSettings) => {
            setBotSettings(newSettings);
            setAutoTrading(newSettings.auto_trade_enabled);
          }}
        />
      )}

      {/* Token Search Modal */}
      <TokenSearch 
        isOpen={showSearch}
        onClose={() => setShowSearch(false)}
        onSelectToken={handleTokenSelect}
      />
    </div>
  );
};

export default Dashboard;
