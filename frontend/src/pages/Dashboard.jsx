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
  CheckCircle,
  Clock,
  DollarSign,
  Layers,
  Eye
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import TokenScanner from '../components/TokenScanner';
import ActiveTrades from '../components/ActiveTrades';
import TradingOpportunities from '../components/TradingOpportunities';
import SettingsPanel from '../components/SettingsPanel';

const Dashboard = () => {
  const { logout, paperMode, togglePaperMode, solPrice, API_URL } = useApp();
  const { connected, publicKey } = useWallet();
  const { connection } = useConnection();
  
  const [walletBalance, setWalletBalance] = useState(0);
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [showSettings, setShowSettings] = useState(false);

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

  // Fetch portfolio data
  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/portfolio`);
      setPortfolio(response.data);
    } catch (error) {
      console.error('Error fetching portfolio:', error);
    }
    setLoading(false);
  }, [API_URL]);

  useEffect(() => {
    fetchWalletBalance();
    fetchPortfolio();
    
    const interval = setInterval(() => {
      fetchWalletBalance();
      fetchPortfolio();
    }, 30000);
    
    return () => clearInterval(interval);
  }, [fetchWalletBalance, fetchPortfolio]);

  const formatUSD = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const formatSOL = (value) => {
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
            
            {/* Paper Mode Toggle */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0A0A0A] border border-[#1E293B] rounded-sm">
              <span className={`text-xs uppercase tracking-wider ${paperMode ? 'text-neon-cyan' : 'text-neon-red'}`}>
                {paperMode ? 'Paper Mode' : 'Live Mode'}
              </span>
              <Switch 
                checked={!paperMode} 
                onCheckedChange={togglePaperMode}
                data-testid="paper-mode-toggle"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* Wallet Balance */}
          <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="wallet-balance-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Wallet Balance</span>
                <Wallet className="w-4 h-4 text-neon-cyan" />
              </div>
              <div className="font-mono text-2xl font-bold text-neon-cyan">
                {connected ? formatSOL(walletBalance) : '--'}
              </div>
              <div className="text-sm text-muted-foreground">
                {connected ? formatUSD(walletBalance * solPrice) : 'Connect wallet'}
              </div>
            </CardContent>
          </Card>

          {/* Portfolio Value */}
          <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="portfolio-value-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Portfolio Value</span>
                <Layers className="w-4 h-4 text-neon-violet" />
              </div>
              <div className="font-mono text-2xl font-bold">
                {portfolio ? formatSOL(portfolio.total_value_sol) : '--'}
              </div>
              <div className="text-sm text-muted-foreground">
                {portfolio ? formatUSD(portfolio.total_value_sol * solPrice) : '--'}
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
              <div className={`font-mono text-2xl font-bold ${portfolio && portfolio.total_pnl >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                {portfolio ? `${portfolio.total_pnl >= 0 ? '+' : ''}${portfolio.total_pnl_percent.toFixed(1)}%` : '--'}
              </div>
              <div className={`text-sm ${portfolio && portfolio.total_pnl >= 0 ? 'text-neon-green/70' : 'text-neon-red/70'}`}>
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
              <div className="font-mono text-2xl font-bold">
                {portfolio ? `${portfolio.win_rate.toFixed(1)}%` : '--'}
              </div>
              <div className="text-sm text-muted-foreground">
                {portfolio ? `${portfolio.closed_trades} trades closed` : '--'}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="bg-[#0A0A0A] border border-[#1E293B]">
            <TabsTrigger value="overview" data-testid="tab-overview">
              <Activity className="w-4 h-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="scanner" data-testid="tab-scanner">
              <Eye className="w-4 h-4 mr-2" />
              Token Scanner
            </TabsTrigger>
            <TabsTrigger value="trades" data-testid="tab-trades">
              <BarChart3 className="w-4 h-4 mr-2" />
              Active Trades
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Trading Opportunities */}
              <TradingOpportunities />
              
              {/* Active Trades Summary */}
              <ActiveTrades compact />
            </div>
          </TabsContent>

          <TabsContent value="scanner">
            <TokenScanner />
          </TabsContent>

          <TabsContent value="trades">
            <ActiveTrades />
          </TabsContent>
        </Tabs>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
};

export default Dashboard;
