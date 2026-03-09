import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { 
  BarChart3, 
  TrendingUp, 
  TrendingDown, 
  X, 
  Clock,
  Target,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  ExternalLink,
  DollarSign,
  Percent,
  ChevronRight,
  Calendar,
  Info,
  Award,
  Timer,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Progress } from './ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { toast } from 'sonner';

// Trade Details Modal Component
const TradeDetailsModal = ({ trade, onClose, solPrice, t }) => {
  if (!trade) return null;
  
  const pnl = trade.pnl || 0;
  const isProfitable = pnl >= 0;
  const roi = trade.pnl_percent || ((trade.price_exit - trade.price_entry) / trade.price_entry * 100);
  
  const formatTime = (timestamp) => {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    return date.toLocaleString('de-DE', { 
      day: '2-digit', 
      month: '2-digit', 
      year: '2-digit',
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  };
  
  const formatDuration = (start, end) => {
    if (!start || !end) return '--';
    const diff = new Date(end) - new Date(start);
    const hours = Math.floor(diff / 3600000);
    const mins = Math.floor((diff % 3600000) / 60000);
    const secs = Math.floor((diff % 60000) / 1000);
    
    if (hours > 0) return `${hours}h ${mins}m`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-[#0A0A0A] border border-[#1E293B] rounded-sm w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1E293B]">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold ${
              isProfitable ? 'bg-neon-green/20 text-neon-green' : 'bg-neon-red/20 text-neon-red'
            }`}>
              {trade.token_symbol?.charAt(0) || '?'}
            </div>
            <div>
              <h3 className="font-heading font-bold">{trade.token_symbol}</h3>
              <p className="text-xs text-muted-foreground">{trade.token_name}</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* P&L Summary */}
        <div className={`p-4 ${isProfitable ? 'bg-neon-green/5' : 'bg-neon-red/5'}`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted-foreground mb-1">{t('trades.pnl')}</div>
              <div className={`text-2xl font-mono font-bold ${isProfitable ? 'text-neon-green' : 'text-neon-red'}`}>
                {pnl >= 0 ? '+' : ''}{pnl.toFixed(6)} SOL
              </div>
              <div className="text-sm text-muted-foreground">
                ≈ ${(pnl * solPrice).toFixed(2)} USD
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-muted-foreground mb-1">{t('trades.roi')}</div>
              <div className={`text-xl font-mono font-bold ${isProfitable ? 'text-neon-green' : 'text-neon-red'}`}>
                {roi >= 0 ? '+' : ''}{roi.toFixed(2)}%
              </div>
              <Badge className={isProfitable ? 'bg-neon-green/20 text-neon-green border-none' : 'bg-neon-red/20 text-neon-red border-none'}>
                {isProfitable ? (
                  <><TrendingUp className="w-3 h-3 mr-1" />{t('trades.profitableTrade')}</>
                ) : (
                  <><TrendingDown className="w-3 h-3 mr-1" />{t('trades.losingTrade')}</>
                )}
              </Badge>
            </div>
          </div>
        </div>

        {/* Trade Details */}
        <div className="p-4 space-y-4">
          {/* Prices */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                <ArrowUpRight className="w-3 h-3" />
                {t('trades.entry')}
              </div>
              <div className="font-mono font-bold text-neon-cyan">
                ${trade.price_entry?.toFixed(10) || '0.00'}
              </div>
            </div>
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                <ArrowDownRight className="w-3 h-3" />
                {t('trades.exit')}
              </div>
              <div className="font-mono font-bold">
                ${trade.price_exit?.toFixed(10) || trade.price_current?.toFixed(10) || '0.00'}
              </div>
            </div>
          </div>

          {/* Size & Time */}
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="text-xs text-muted-foreground mb-1">{t('trades.size')}</div>
              <div className="font-mono font-bold">{trade.amount_sol?.toFixed(4)} SOL</div>
            </div>
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="text-xs text-muted-foreground mb-1">{t('trades.duration')}</div>
              <div className="font-mono font-bold">
                {formatDuration(trade.opened_at || trade.created_at, trade.closed_at)}
              </div>
            </div>
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="text-xs text-muted-foreground mb-1">{t('trades.type')}</div>
              <Badge variant="outline" className={trade.paper_trade ? 'border-neon-cyan/30 text-neon-cyan' : 'border-neon-green/30 text-neon-green'}>
                {trade.paper_trade ? t('trades.paper') : t('trades.live')}
              </Badge>
            </div>
          </div>

          {/* Times */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                <Calendar className="w-3 h-3" />
                {t('trades.timeOpened')}
              </div>
              <div className="font-mono text-sm">{formatTime(trade.opened_at || trade.created_at)}</div>
            </div>
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                <CheckCircle className="w-3 h-3" />
                {t('trades.timeClosed')}
              </div>
              <div className="font-mono text-sm">{formatTime(trade.closed_at)}</div>
            </div>
          </div>

          {/* Close Reason */}
          {trade.close_reason && (
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="text-xs text-muted-foreground mb-1">Grund</div>
              <Badge className={`${
                trade.close_reason === 'TAKE_PROFIT' ? 'bg-neon-green/20 text-neon-green' :
                trade.close_reason === 'STOP_LOSS' ? 'bg-neon-red/20 text-neon-red' :
                'bg-neon-yellow/20 text-neon-yellow'
              } border-none`}>
                {trade.close_reason === 'TAKE_PROFIT' ? t('trades.takeProfitHit') :
                 trade.close_reason === 'STOP_LOSS' ? t('trades.stopLossHit') :
                 t('trades.manualClose')}
              </Badge>
            </div>
          )}

          {/* Transaction Links */}
          <div className="flex gap-2">
            {trade.entry_tx && (
              <Button 
                variant="outline" 
                size="sm" 
                className="flex-1"
                onClick={() => window.open(`https://solscan.io/tx/${trade.entry_tx}`, '_blank')}
              >
                <ExternalLink className="w-3 h-3 mr-2" />
                {t('trades.entryTx')}
              </Button>
            )}
            {trade.exit_tx && (
              <Button 
                variant="outline" 
                size="sm" 
                className="flex-1"
                onClick={() => window.open(`https://solscan.io/tx/${trade.exit_tx}`, '_blank')}
              >
                <ExternalLink className="w-3 h-3 mr-2" />
                {t('trades.exitTx')}
              </Button>
            )}
            <Button 
              variant="outline" 
              size="sm" 
              className="flex-1"
              onClick={() => window.open(`https://dexscreener.com/solana/${trade.pair_address || trade.token_address}`, '_blank')}
            >
              <BarChart3 className="w-3 h-3 mr-2" />
              {t('trades.viewChart')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const LiveTradesPanel = ({ solPrice = 150, compact = false, onTradeUpdate }) => {
  const { t } = useTranslation();
  const { API_URL } = useApp();
  const [openTrades, setOpenTrades] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('open');
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [closedStats, setClosedStats] = useState({
    totalTrades: 0,
    totalProfit: 0,
    totalLoss: 0,
    winRate: 0,
    avgProfit: 0,
    avgLoss: 0
  });
  const [stats, setStats] = useState({
    totalInvested: 0,
    currentValue: 0,
    totalPnl: 0,
    totalPnlPercent: 0
  });

  const fetchTrades = useCallback(async () => {
    try {
      const [openRes, closedRes] = await Promise.all([
        axios.get(`${API_URL}/trades`, { params: { status: 'OPEN' } }),
        axios.get(`${API_URL}/trades`, { params: { status: 'CLOSED' } })
      ]);
      
      setOpenTrades(openRes.data);
      setClosedTrades(closedRes.data);
      
      // Calculate open trades stats
      const invested = openRes.data.reduce((sum, t) => sum + t.amount_sol, 0);
      const currentValue = openRes.data.reduce((sum, t) => {
        const pnlPercent = ((t.price_current / t.price_entry) - 1) * 100;
        return sum + t.amount_sol * (1 + pnlPercent / 100);
      }, 0);
      
      setStats({
        totalInvested: invested,
        currentValue: currentValue,
        totalPnl: currentValue - invested,
        totalPnlPercent: invested > 0 ? ((currentValue - invested) / invested) * 100 : 0
      });
      
      // Calculate closed trades stats
      const closed = closedRes.data;
      const winners = closed.filter(t => (t.pnl || 0) > 0);
      const losers = closed.filter(t => (t.pnl || 0) < 0);
      const totalProfit = winners.reduce((sum, t) => sum + (t.pnl || 0), 0);
      const totalLoss = Math.abs(losers.reduce((sum, t) => sum + (t.pnl || 0), 0));
      
      setClosedStats({
        totalTrades: closed.length,
        totalProfit: totalProfit,
        totalLoss: totalLoss,
        winRate: closed.length > 0 ? (winners.length / closed.length) * 100 : 0,
        avgProfit: winners.length > 0 ? totalProfit / winners.length : 0,
        avgLoss: losers.length > 0 ? totalLoss / losers.length : 0
      });
      
      if (onTradeUpdate) {
        onTradeUpdate({ open: openRes.data.length, closed: closedRes.data.length });
      }
    } catch (error) {
      console.error('Error fetching trades:', error);
    } finally {
      setLoading(false);
    }
  }, [API_URL, onTradeUpdate]);

  // Real-time price update for open trades
  const updatePrices = useCallback(async () => {
    try {
      const response = await axios.post(`${API_URL}/trades/update-all-prices`);
      const data = response.data;
      
      console.log('Price update response:', data);
      
      if (data.updated > 0 && data.trades?.length > 0) {
        // Get fresh trades list
        const freshTradesRes = await axios.get(`${API_URL}/trades`, { params: { status: 'OPEN' } });
        const freshTrades = freshTradesRes.data;
        
        // Update with latest prices from the response
        const updatedTrades = freshTrades.map(trade => {
          const update = data.trades.find(u => u.id === trade.id);
          if (update) {
            return {
              ...trade,
              price_current: update.price_current,
              pnl: update.pnl,
              pnl_percent: update.pnl_percent
            };
          }
          return trade;
        });
        
        // Filter out any that were auto-closed
        const stillOpen = updatedTrades.filter(t => {
          const update = data.trades.find(u => u.id === t.id);
          return !update?.should_close;
        });
        
        setOpenTrades(stillOpen);
        
        // Recalculate stats
        const invested = stillOpen.reduce((sum, t) => sum + (t.amount_sol || 0), 0);
        const currentValue = stillOpen.reduce((sum, t) => {
          const entry = t.price_entry || 1;
          const current = t.price_current || entry;
          const pnlPercent = ((current / entry) - 1) * 100;
          return sum + (t.amount_sol || 0) * (1 + pnlPercent / 100);
        }, 0);
        
        setStats({
          totalInvested: invested,
          currentValue: currentValue,
          totalPnl: currentValue - invested,
          totalPnlPercent: invested > 0 ? ((currentValue - invested) / invested) * 100 : 0
        });
        
        // If any trades were auto-closed, refresh closed trades
        if (data.closed > 0) {
          const closedRes = await axios.get(`${API_URL}/trades`, { params: { status: 'CLOSED' } });
          setClosedTrades(closedRes.data);
        }
      }
    } catch (error) {
      console.error('Price update error:', error);
    }
  }, [API_URL]);  // Remove openTrades dependency to avoid stale closures

  useEffect(() => {
    fetchTrades();
    // Fetch trades every 5 seconds
    const fetchInterval = setInterval(fetchTrades, 5000);
    return () => clearInterval(fetchInterval);
  }, [fetchTrades]);

  // Real-time price updates every 2.5 seconds for smoother updates
  useEffect(() => {
    // Initial update
    const timer = setTimeout(updatePrices, 1000);
    
    // Regular interval
    const priceInterval = setInterval(updatePrices, 2500);
    
    return () => {
      clearTimeout(timer);
      clearInterval(priceInterval);
    };
  }, [updatePrices]);

  const closeTrade = async (tradeId) => {
    try {
      const response = await axios.post(`${API_URL}/trades/${tradeId}/close`);
      const data = response.data;
      
      if (data.success) {
        const pnlText = data.pnl >= 0 ? `+${data.pnl.toFixed(6)}` : data.pnl.toFixed(6);
        const roiText = data.pnl_percent >= 0 ? `+${data.pnl_percent.toFixed(2)}` : data.pnl_percent.toFixed(2);
        
        toast.success(t('trades.closeTrade'), {
          description: `P&L: ${pnlText} SOL (${roiText}%)`
        });
      } else {
        toast.success(t('trades.closeTrade'));
      }
      
      fetchTrades();
    } catch (error) {
      console.error('Close trade error:', error);
      const errorMessage = error.response?.data?.detail || t('errors.tradeFailed');
      toast.error(t('errors.tradeFailed'), {
        description: errorMessage
      });
    }
  };

  const formatPrice = (price) => {
    if (!price) return '$0.00';
    if (price < 0.0001) return `$${price.toExponential(2)}`;
    if (price < 1) return `$${price.toFixed(8)}`;
    return `$${price.toFixed(4)}`;
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  };

  const getPnlColor = (value) => {
    if (value > 0) return 'text-neon-green';
    if (value < 0) return 'text-neon-red';
    return 'text-muted-foreground';
  };

  // Compact view for sidebar
  if (compact) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B] h-full" data-testid="live-trades-compact">
        <CardHeader className="border-b border-[#1E293B] pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-neon-violet" />
              <CardTitle className="font-heading text-base">{t('trades.activeTrades')}</CardTitle>
              <Badge variant="outline" className="border-neon-violet/30 text-neon-violet">
                {openTrades.length}
              </Badge>
            </div>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={fetchTrades}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-2">
          {openTrades.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">{t('trades.noActiveTrades')}</p>
            </div>
          ) : (
            <ScrollArea className="h-[300px]">
              <div className="space-y-2">
                {openTrades.slice(0, 10).map((trade) => {
                  const pnlPercent = ((trade.price_current / trade.price_entry) - 1) * 100;
                  const pnlSol = trade.amount_sol * (pnlPercent / 100);
                  
                  return (
                    <div 
                      key={trade.id}
                      className="p-3 bg-[#050505] rounded-sm border border-[#1E293B] hover:border-neon-violet/30 transition-colors cursor-pointer"
                      onClick={() => setSelectedTrade(trade)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-neon-violet/20 flex items-center justify-center text-xs font-bold text-neon-violet">
                            {trade.token_symbol?.charAt(0) || '?'}
                          </div>
                          <span className="font-medium text-sm">{trade.token_symbol}</span>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-6 w-6"
                          onClick={(e) => { e.stopPropagation(); closeTrade(trade.id); }}
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                        <div>
                          <span className="text-muted-foreground">{t('trades.entry')}: </span>
                          <span className="font-mono">{formatPrice(trade.price_entry)}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">{t('trades.now')}: </span>
                          <span className="font-mono">{formatPrice(trade.price_current)}</span>
                        </div>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <div className={`font-mono font-bold ${getPnlColor(pnlPercent)}`}>
                          {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                        </div>
                        <div className={`text-xs font-mono ${getPnlColor(pnlSol)}`}>
                          {pnlSol >= 0 ? '+' : ''}{pnlSol.toFixed(6)} SOL
                        </div>
                        <Badge variant="outline" className={`text-xs ${trade.paper_trade ? 'border-neon-cyan/30 text-neon-cyan' : 'border-neon-green/30 text-neon-green'}`}>
                          {trade.paper_trade ? t('trades.paper') : t('trades.live')}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </CardContent>
        
        {selectedTrade && (
          <TradeDetailsModal 
            trade={selectedTrade} 
            onClose={() => setSelectedTrade(null)} 
            solPrice={solPrice}
            t={t}
          />
        )}
      </Card>
    );
  }

  // Full view
  return (
    <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="live-trades-panel">
      <CardHeader className="border-b border-[#1E293B]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-neon-violet" />
            <CardTitle className="font-heading">Live P&L Monitor</CardTitle>
          </div>
          <Button 
            variant="outline" 
            size="icon" 
            onClick={fetchTrades}
            disabled={loading}
            data-testid="refresh-trades"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        
        {/* Portfolio Summary */}
        <div className="grid grid-cols-4 gap-3 mt-4">
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="text-xs text-muted-foreground mb-1">{t('trades.totalInvested')}</div>
            <div className="font-mono font-bold text-neon-cyan">
              {stats.totalInvested.toFixed(4)} SOL
            </div>
            <div className="text-xs text-muted-foreground">
              ≈ ${(stats.totalInvested * solPrice).toFixed(2)}
            </div>
          </div>
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="text-xs text-muted-foreground mb-1">{t('trades.currentValue')}</div>
            <div className="font-mono font-bold">
              {stats.currentValue.toFixed(4)} SOL
            </div>
            <div className="text-xs text-muted-foreground">
              ≈ ${(stats.currentValue * solPrice).toFixed(2)}
            </div>
          </div>
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="text-xs text-muted-foreground mb-1">{t('trades.pnl')}</div>
            <div className={`font-mono font-bold ${getPnlColor(stats.totalPnl)}`}>
              {stats.totalPnl >= 0 ? '+' : ''}{stats.totalPnl.toFixed(4)} SOL
            </div>
            <div className={`text-xs ${getPnlColor(stats.totalPnl)}`}>
              {stats.totalPnlPercent >= 0 ? '+' : ''}{stats.totalPnlPercent.toFixed(2)}%
            </div>
          </div>
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="text-xs text-muted-foreground mb-1">{t('trades.netResult')}</div>
            <div className={`font-mono font-bold text-lg ${getPnlColor(stats.currentValue - stats.totalInvested)}`}>
              {stats.currentValue >= stats.totalInvested ? '+' : ''}{(stats.currentValue - stats.totalInvested).toFixed(4)} SOL
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="p-0">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full justify-start px-4 pt-2 bg-transparent border-b border-[#1E293B] rounded-none">
            <TabsTrigger value="open" className="data-[state=active]:bg-[#1E293B]">
              {t('trades.activeTrades')} ({openTrades.length})
            </TabsTrigger>
            <TabsTrigger value="closed" className="data-[state=active]:bg-[#1E293B]">
              {t('trades.closedTrades')} ({closedTrades.length})
            </TabsTrigger>
          </TabsList>

          {/* Active Trades Tab */}
          <TabsContent value="open" className="mt-0">
            {openTrades.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>{t('trades.noActiveTrades')}</p>
              </div>
            ) : (
              <ScrollArea className="h-[400px]">
                <table className="w-full">
                  <thead className="bg-[#050505] sticky top-0">
                    <tr className="text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="text-left p-3">Token</th>
                      <th className="text-right p-3">{t('trades.entry')}</th>
                      <th className="text-right p-3">{t('trades.current')}</th>
                      <th className="text-right p-3">{t('trades.size')}</th>
                      <th className="text-right p-3">{t('trades.pnl')}</th>
                      <th className="text-right p-3">{t('trades.roi')}</th>
                      <th className="text-right p-3">{t('trades.type')}</th>
                      <th className="text-center p-3"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E293B]">
                    {openTrades.map((trade) => {
                      const pnlPercent = ((trade.price_current / trade.price_entry) - 1) * 100;
                      const pnlSol = trade.amount_sol * (pnlPercent / 100);
                      
                      return (
                        <tr 
                          key={trade.id} 
                          className="hover:bg-[#050505] cursor-pointer transition-colors"
                          onClick={() => setSelectedTrade(trade)}
                        >
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <div className="w-8 h-8 rounded-full bg-neon-violet/20 flex items-center justify-center text-sm font-bold text-neon-violet">
                                {trade.token_symbol?.charAt(0) || '?'}
                              </div>
                              <div>
                                <div className="font-medium">{trade.token_symbol}</div>
                                <div className="text-xs text-muted-foreground">{trade.token_name?.slice(0, 20)}</div>
                              </div>
                            </div>
                          </td>
                          <td className="p-3 text-right font-mono text-sm">{formatPrice(trade.price_entry)}</td>
                          <td className="p-3 text-right font-mono text-sm">{formatPrice(trade.price_current)}</td>
                          <td className="p-3 text-right font-mono text-sm">{trade.amount_sol?.toFixed(4)} SOL</td>
                          <td className={`p-3 text-right font-mono font-bold ${getPnlColor(pnlSol)}`}>
                            {pnlSol >= 0 ? '+' : ''}{pnlSol.toFixed(6)} SOL
                          </td>
                          <td className={`p-3 text-right font-mono font-bold ${getPnlColor(pnlPercent)}`}>
                            {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                          </td>
                          <td className="p-3 text-right">
                            <Badge variant="outline" className={trade.paper_trade ? 'border-neon-cyan/30 text-neon-cyan' : 'border-neon-green/30 text-neon-green'}>
                              {trade.paper_trade ? t('trades.paper') : t('trades.live')}
                            </Badge>
                          </td>
                          <td className="p-3 text-center">
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-7 w-7"
                              onClick={(e) => { e.stopPropagation(); closeTrade(trade.id); }}
                            >
                              <X className="w-4 h-4" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </ScrollArea>
            )}
          </TabsContent>

          {/* Closed Trades Tab */}
          <TabsContent value="closed" className="mt-0">
            {/* Closed Trades Summary Stats */}
            <div className="grid grid-cols-6 gap-3 p-4 border-b border-[#1E293B] bg-[#050505]">
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t('trades.closedTrades')}</div>
                <div className="font-mono font-bold text-lg">{closedStats.totalTrades}</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t('trades.totalProfit')}</div>
                <div className="font-mono font-bold text-lg text-neon-green">
                  +{closedStats.totalProfit.toFixed(4)} SOL
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t('trades.totalLoss')}</div>
                <div className="font-mono font-bold text-lg text-neon-red">
                  -{closedStats.totalLoss.toFixed(4)} SOL
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t('trades.winRate')}</div>
                <div className="font-mono font-bold text-lg text-neon-cyan">
                  {closedStats.winRate.toFixed(0)}%
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t('trades.avgProfit')}</div>
                <div className="font-mono font-bold text-neon-green">
                  +{closedStats.avgProfit.toFixed(6)} SOL
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground mb-1">{t('trades.avgLoss')}</div>
                <div className="font-mono font-bold text-neon-red">
                  -{closedStats.avgLoss.toFixed(6)} SOL
                </div>
              </div>
            </div>

            {closedTrades.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <CheckCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>{t('trades.noClosedTrades')}</p>
              </div>
            ) : (
              <ScrollArea className="h-[400px]">
                <table className="w-full">
                  <thead className="bg-[#050505] sticky top-0">
                    <tr className="text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="text-left p-3">Token</th>
                      <th className="text-right p-3">{t('trades.entry')}</th>
                      <th className="text-right p-3">{t('trades.exit')}</th>
                      <th className="text-right p-3">{t('trades.size')}</th>
                      <th className="text-right p-3">{t('trades.pnl')}</th>
                      <th className="text-right p-3">{t('trades.roi')}</th>
                      <th className="text-center p-3">{t('trades.timeOpened')}</th>
                      <th className="text-center p-3">{t('trades.timeClosed')}</th>
                      <th className="text-center p-3"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E293B]">
                    {closedTrades.map((trade) => {
                      const pnl = trade.pnl || 0;
                      const roi = trade.pnl_percent || ((trade.price_exit - trade.price_entry) / trade.price_entry * 100);
                      const isProfitable = pnl >= 0;
                      
                      return (
                        <tr 
                          key={trade.id} 
                          className={`hover:bg-[#050505] cursor-pointer transition-colors ${
                            isProfitable ? 'bg-neon-green/5' : 'bg-neon-red/5'
                          }`}
                          onClick={() => setSelectedTrade(trade)}
                        >
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                                isProfitable ? 'bg-neon-green/20 text-neon-green' : 'bg-neon-red/20 text-neon-red'
                              }`}>
                                {isProfitable ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                              </div>
                              <div>
                                <div className="font-medium">{trade.token_symbol}</div>
                                <div className="text-xs text-muted-foreground">{trade.token_name?.slice(0, 20)}</div>
                              </div>
                            </div>
                          </td>
                          <td className="p-3 text-right font-mono text-sm">{formatPrice(trade.price_entry)}</td>
                          <td className="p-3 text-right font-mono text-sm">{formatPrice(trade.price_exit)}</td>
                          <td className="p-3 text-right font-mono text-sm">{trade.amount_sol?.toFixed(4)} SOL</td>
                          <td className={`p-3 text-right font-mono font-bold ${getPnlColor(pnl)}`}>
                            {pnl >= 0 ? '+' : ''}{pnl.toFixed(6)} SOL
                          </td>
                          <td className={`p-3 text-right font-mono font-bold ${getPnlColor(roi)}`}>
                            {roi >= 0 ? '+' : ''}{roi.toFixed(2)}%
                          </td>
                          <td className="p-3 text-center">
                            <div className="text-xs">
                              <div>{formatTime(trade.opened_at || trade.created_at)}</div>
                              <div className="text-muted-foreground">{formatDate(trade.opened_at || trade.created_at)}</div>
                            </div>
                          </td>
                          <td className="p-3 text-center">
                            <div className="text-xs">
                              <div>{formatTime(trade.closed_at)}</div>
                              <div className="text-muted-foreground">{formatDate(trade.closed_at)}</div>
                            </div>
                          </td>
                          <td className="p-3 text-center">
                            <ChevronRight className="w-4 h-4 text-muted-foreground" />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </ScrollArea>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
      
      {/* Trade Details Modal */}
      {selectedTrade && (
        <TradeDetailsModal 
          trade={selectedTrade} 
          onClose={() => setSelectedTrade(null)} 
          solPrice={solPrice}
          t={t}
        />
      )}
    </Card>
  );
};

export default LiveTradesPanel;
