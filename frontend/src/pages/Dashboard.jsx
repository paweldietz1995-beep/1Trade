import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useApp } from '../context/AppContext';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { LAMPORTS_PER_SOL, Connection } from '@solana/web3.js';
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
  Radio,
  Power,
  StopCircle,
  AlertCircle,
  Wifi,
  WifiOff
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import TokenScanner from '../components/TokenScanner';
import TradingOpportunities from '../components/TradingOpportunities';
import BotSettingsPanel from '../components/BotSettingsPanel';
import WalletPanel from '../components/WalletPanel';
import TokenSearch from '../components/TokenSearch';
import TradingViewWidget from '../components/TradingViewWidget';
import LiveTradesPanel from '../components/LiveTradesPanel';
import DebugPanel from '../components/DebugPanel';
import { toast } from 'sonner';

const TRADING_MODES = {
  PAPER: 'paper',
  LIVE: 'live'
};

// RPC Endpoints for failover
const RPC_ENDPOINTS = [
  'https://rpc.ankr.com/solana',
  'https://api.mainnet-beta.solana.com'
];

const Dashboard = () => {
  const { logout, API_URL } = useApp();
  const { connected, publicKey, connecting } = useWallet();
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
  const [autoTradingActive, setAutoTradingActive] = useState(false);
  const [tradingMode, setTradingMode] = useState(TRADING_MODES.PAPER);
  const [showLiveModeWarning, setShowLiveModeWarning] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const [rpcStatus, setRpcStatus] = useState({ healthy: true, endpoint: null });
  const autoTradingIntervalRef = useRef(null);
  const currentRpcIndexRef = useRef(0);

  // Debug wallet state
  useEffect(() => {
    console.log('📊 Dashboard Wallet State:', {
      connected,
      connecting,
      publicKey: publicKey?.toBase58(),
      walletBalance,
      rpcEndpoint: RPC_ENDPOINTS[currentRpcIndexRef.current]?.substring(0, 30)
    });
  }, [connected, connecting, publicKey, walletBalance]);

  // Create connection with specific endpoint
  const createConnection = useCallback((endpointIndex) => {
    const endpoint = RPC_ENDPOINTS[endpointIndex];
    return new Connection(endpoint, {
      commitment: 'confirmed',
      confirmTransactionInitialTimeout: 15000
    });
  }, []);

  // Fetch wallet balance with failover
  const fetchWalletBalance = useCallback(async () => {
    if (!connected || !publicKey) {
      setWalletBalance(0);
      return;
    }
    
    // Try each endpoint
    for (let i = 0; i < RPC_ENDPOINTS.length; i++) {
      const endpointIndex = (currentRpcIndexRef.current + i) % RPC_ENDPOINTS.length;
      
      try {
        console.log(`💰 Fetching wallet balance from endpoint ${endpointIndex + 1}...`);
        const conn = createConnection(endpointIndex);
        
        const balancePromise = conn.getBalance(publicKey);
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Timeout')), 10000)
        );
        
        const balance = await Promise.race([balancePromise, timeoutPromise]);
        const solBalance = balance / LAMPORTS_PER_SOL;
        
        console.log(`✅ Wallet Balance: ${solBalance} SOL`);
        setWalletBalance(solBalance);
        setRpcStatus({ healthy: true, endpoint: RPC_ENDPOINTS[endpointIndex] });
        currentRpcIndexRef.current = endpointIndex;
        return;
        
      } catch (error) {
        console.warn(`❌ RPC ${endpointIndex + 1} failed:`, error.message);
        
        if (i === RPC_ENDPOINTS.length - 1) {
          console.error('❌ All RPC endpoints failed for balance fetch');
          setRpcStatus({ healthy: false, endpoint: null });
        }
      }
    }
  }, [connected, publicKey, createConnection]);

  // Fetch portfolio and settings
  const fetchData = useCallback(async () => {
    try {
      console.log('📡 Fetching portfolio and settings...');
      const [portfolioRes, settingsRes] = await Promise.all([
        axios.get(`${API_URL}/portfolio`),
        axios.get(`${API_URL}/bot/settings`)
      ]);
      setPortfolio(portfolioRes.data);
      setBotSettings(settingsRes.data);
      setTradingMode(settingsRes.data.paper_mode ? TRADING_MODES.PAPER : TRADING_MODES.LIVE);
      console.log('✅ Data fetched:', { portfolio: portfolioRes.data, settings: settingsRes.data });
    } catch (error) {
      console.error('❌ Error fetching data:', error);
    }
    setLoading(false);
  }, [API_URL]);

  // Fetch SOL price
  const fetchSolPrice = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/market/sol-price`);
      setSolPrice(response.data.price || 150);
    } catch (error) {
      console.warn('⚠️ Error fetching SOL price:', error);
    }
  }, [API_URL]);

  useEffect(() => {
    fetchWalletBalance();
    fetchData();
    fetchSolPrice();
    
    // Wallet balance every 10 seconds
    const walletInterval = setInterval(fetchWalletBalance, 10000);
    // Portfolio every 15 seconds
    const portfolioInterval = setInterval(fetchData, 15000);
    // SOL price every 60 seconds
    const priceInterval = setInterval(fetchSolPrice, 60000);
    
    return () => {
      clearInterval(walletInterval);
      clearInterval(portfolioInterval);
      clearInterval(priceInterval);
    };
  }, [fetchWalletBalance, fetchData, fetchSolPrice]);

  // Handle trading mode toggle with safety check
  const handleTradingModeToggle = async (newMode) => {
    if (newMode === TRADING_MODES.LIVE) {
      // Check if live trading can be safely enabled
      try {
        const response = await axios.get(`${API_URL}/trading/can-enable-live`);
        const check = response.data;
        
        if (!check.can_enable) {
          toast.error('Cannot enable live trading', {
            description: check.blockers[0] || 'System check failed'
          });
          return;
        }
        
        // Show warnings if any
        if (check.warnings?.length > 0) {
          check.warnings.forEach(w => {
            toast.warning('Warning', { description: w });
          });
        }
        
        setShowLiveModeWarning(true);
      } catch (error) {
        toast.error('Safety check failed', {
          description: 'Unable to verify system status'
        });
      }
    } else {
      updateTradingMode(TRADING_MODES.PAPER);
    }
  };

  const updateTradingMode = async (mode) => {
    try {
      const isPaperMode = mode === TRADING_MODES.PAPER;
      const newSettings = { ...botSettings, paper_mode: isPaperMode };
      await axios.put(`${API_URL}/bot/settings`, newSettings);
      setBotSettings(newSettings);
      setTradingMode(mode);
      
      toast.success(
        isPaperMode ? '🧪 Paper Mode Activated' : '🚀 Live Trading Activated',
        { description: isPaperMode ? 'Trades will be simulated' : 'Real funds will be used!' }
      );
    } catch (error) {
      toast.error('Failed to update trading mode');
    }
  };

  const confirmLiveMode = () => {
    updateTradingMode(TRADING_MODES.LIVE);
    setShowLiveModeWarning(false);
  };

  // Auto Trading Logic - Now uses backend engine
  const executeAutoTrade = useCallback(async () => {
    if (!autoTradingActive || !botSettings) return;
    
    try {
      // Fetch status from backend auto trading engine
      const statusRes = await axios.get(`${API_URL}/auto-trading/status`);
      const status = statusRes.data;
      
      console.log('🤖 Auto Trading Status:', status);
      
      // Update UI with latest data
      fetchData();
      fetchWalletBalance();
      
    } catch (error) {
      console.error('❌ Auto trade status error:', error);
    }
  }, [autoTradingActive, botSettings, API_URL, fetchData, fetchWalletBalance]);

  const startAutoTrading = async () => {
    if (!botSettings) return;
    
    try {
      console.log('🚀 Starting Auto Trading Engine...');
      
      // Start backend auto trading engine
      const response = await axios.post(`${API_URL}/auto-trading/start`);
      
      if (response.data.success) {
        setAutoTradingActive(true);
        
        // Set up interval to check status and update UI
        autoTradingIntervalRef.current = setInterval(executeAutoTrade, 3000);
        
        toast.success('🤖 Auto Trading Engine Started', {
          description: `Scanning every 3 seconds | Mode: ${tradingMode.toUpperCase()}`
        });
      } else {
        toast.error('Failed to start auto trading', {
          description: response.data.message
        });
      }
    } catch (error) {
      console.error('Error starting auto trading:', error);
      toast.error('Failed to start auto trading');
    }
  };

  const stopAutoTrading = async () => {
    console.log('🛑 Stopping Auto Trading Engine...');
    
    try {
      // Stop backend auto trading engine
      const response = await axios.post(`${API_URL}/auto-trading/stop`);
      
      if (autoTradingIntervalRef.current) {
        clearInterval(autoTradingIntervalRef.current);
        autoTradingIntervalRef.current = null;
      }
      
      setAutoTradingActive(false);
      
      toast.info('🛑 Auto Trading Stopped', {
        description: `Scans: ${response.data.stats?.scan_count || 0} | Trades: ${response.data.stats?.trades_executed || 0}`
      });
    } catch (error) {
      console.error('Error stopping auto trading:', error);
      // Still stop locally
      if (autoTradingIntervalRef.current) {
        clearInterval(autoTradingIntervalRef.current);
        autoTradingIntervalRef.current = null;
      }
      setAutoTradingActive(false);
    }
  };

  const toggleAutoTrading = () => {
    if (autoTradingActive) {
      stopAutoTrading();
    } else {
      startAutoTrading();
    }
  };

  // Cleanup
  useEffect(() => {
    return () => {
      if (autoTradingIntervalRef.current) {
        clearInterval(autoTradingIntervalRef.current);
      }
    };
  }, []);

  const handleTokenSelect = (token) => {
    setSelectedToken(token);
    setActiveTab('chart');
  };

  const handleWalletBalanceUpdate = (balance) => {
    console.log('📥 Wallet balance update from panel:', balance);
    setWalletBalance(balance);
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
    if (value === null || value === undefined) return '--';
    return `${value.toFixed(4)} SOL`;
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
            
            {/* Trading Mode Toggle */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-sm border ${
              tradingMode === TRADING_MODES.LIVE 
                ? 'bg-neon-red/10 border-neon-red/30' 
                : 'bg-neon-cyan/10 border-neon-cyan/30'
            }`}>
              <span className={`text-xs uppercase tracking-wider ${
                tradingMode === TRADING_MODES.LIVE ? 'text-neon-red' : 'text-neon-cyan'
              }`}>
                {tradingMode === TRADING_MODES.LIVE ? '🔴 LIVE' : '🧪 PAPER'}
              </span>
              <Switch 
                checked={tradingMode === TRADING_MODES.LIVE}
                onCheckedChange={(checked) => handleTradingModeToggle(checked ? TRADING_MODES.LIVE : TRADING_MODES.PAPER)}
                data-testid="trading-mode-toggle"
              />
            </div>
            
            {/* Auto Trading Control */}
            <Button
              variant={autoTradingActive ? 'default' : 'outline'}
              size="sm"
              onClick={toggleAutoTrading}
              className={`${autoTradingActive 
                ? 'bg-neon-green text-black hover:bg-neon-green/90' 
                : 'border-neon-green/30 text-neon-green hover:bg-neon-green/10'
              }`}
              data-testid="auto-trade-toggle"
            >
              {autoTradingActive ? (
                <>
                  <StopCircle className="w-4 h-4 mr-2" />
                  Stop Auto Trade
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Start Auto Trade
                </>
              )}
            </Button>
            
            {autoTradingActive && (
              <Badge className="bg-neon-green/20 text-neon-green border-none animate-pulse">
                <Bot className="w-3 h-3 mr-1" />
                ACTIVE
              </Badge>
            )}

            {/* Pause Warning */}
            {portfolio?.is_paused && (
              <Badge className="bg-neon-red/20 text-neon-red border-none animate-pulse">
                <Pause className="w-3 h-3 mr-1" />
                PAUSED
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Debug Panel Button */}
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => setShowDebugPanel(true)}
              className="border-[#1E293B]"
              data-testid="debug-button"
            >
              <Activity className="w-4 h-4 mr-2" />
              Debug
            </Button>

            {/* Search */}
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => setShowSearch(true)}
              className="border-[#1E293B]"
              data-testid="search-button"
            >
              <Search className="w-4 h-4 mr-2" />
              Search
            </Button>

            {/* SOL Price */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0A0A0A] border border-[#1E293B] rounded-sm">
              <span className="text-xs text-muted-foreground uppercase tracking-wider">SOL Price:</span>
              <span className="font-mono text-sm text-neon-green" data-testid="sol-price-header">
                {formatUSD(solPrice)}
              </span>
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
              <div className="font-mono text-xl font-bold text-neon-cyan" data-testid="wallet-balance-display">
                {connected ? formatSOL(walletBalance) : (connecting ? 'Connecting...' : 'Not Connected')}
              </div>
              <div className="text-xs text-muted-foreground">
                {connected ? formatUSD(walletBalance * solPrice) : 'Connect wallet to trade'}
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

        {/* Risk Warning Banner */}
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

        {/* Live Mode Active Warning */}
        {tradingMode === TRADING_MODES.LIVE && (
          <div className="mb-4 p-3 bg-neon-red/10 border border-neon-red/30 rounded-sm flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-neon-red" />
            <span className="text-sm text-neon-red">
              <strong>Live Trading Active:</strong> Real funds will be used for trades. Trade carefully!
            </span>
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
              Live P&L
            </TabsTrigger>
            <TabsTrigger value="chart" data-testid="tab-chart">
              <Eye className="w-4 h-4 mr-2" />
              Chart
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <TradingOpportunities onSelectToken={handleTokenSelect} />
              </div>
              <div className="space-y-4">
                <WalletPanel solPrice={solPrice} onBalanceUpdate={handleWalletBalanceUpdate} />
                <LiveTradesPanel solPrice={solPrice} compact />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="scanner">
            <TokenScanner onSelectToken={handleTokenSelect} />
          </TabsContent>

          <TabsContent value="trades">
            <LiveTradesPanel solPrice={solPrice} />
          </TabsContent>

          <TabsContent value="chart">
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
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
                      symbol={selectedToken ? selectedToken.symbol : null}
                      selectedToken={selectedToken}
                    />
                  </CardContent>
                </Card>
              </div>
              <div>
                <LiveTradesPanel solPrice={solPrice} compact />
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
            setTradingMode(newSettings.paper_mode ? TRADING_MODES.PAPER : TRADING_MODES.LIVE);
          }}
        />
      )}

      {/* Token Search Modal */}
      <TokenSearch 
        isOpen={showSearch}
        onClose={() => setShowSearch(false)}
        onSelectToken={handleTokenSelect}
      />

      {/* Debug Panel */}
      <DebugPanel 
        isOpen={showDebugPanel}
        onClose={() => setShowDebugPanel(false)}
      />

      {/* Live Mode Warning Dialog */}
      <AlertDialog open={showLiveModeWarning} onOpenChange={setShowLiveModeWarning}>
        <AlertDialogContent className="bg-[#0A0A0A] border-[#1E293B]">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-neon-red">
              <AlertTriangle className="w-5 h-5" />
              Enable Live Trading?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              <p className="mb-4">
                You are about to enable <strong className="text-neon-red">LIVE TRADING</strong>. 
                This means real funds from your wallet will be used for trades.
              </p>
              <div className="bg-neon-red/10 border border-neon-red/30 rounded-sm p-3 space-y-2">
                <p className="text-neon-red font-semibold">⚠️ Warning:</p>
                <ul className="list-disc list-inside text-sm space-y-1">
                  <li>Real SOL will be spent on trades</li>
                  <li>Losses are permanent and non-reversible</li>
                  <li>Trading crypto carries significant risk</li>
                  <li>Never trade more than you can afford to lose</li>
                </ul>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-[#1E293B]">Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={confirmLiveMode}
              className="bg-neon-red text-white hover:bg-neon-red/90"
            >
              I Understand, Enable Live Trading
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Dashboard;
