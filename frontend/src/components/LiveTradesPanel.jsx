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
  Percent
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Progress } from './ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { toast } from 'sonner';

const LiveTradesPanel = ({ solPrice = 150, compact = false, onTradeUpdate }) => {
  const { t } = useTranslation();
  const { API_URL } = useApp();
  const [openTrades, setOpenTrades] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('open');
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
      setClosedTrades(closedRes.data.slice(0, 20));
      
      // Calculate stats
      const invested = openRes.data.reduce((sum, t) => sum + t.amount_sol, 0);
      const currentValue = openRes.data.reduce((sum, t) => {
        const pnlPercent = ((t.price_current / t.price_entry) - 1) * 100;
        return sum + t.amount_sol * (1 + pnlPercent / 100);
      }, 0);
      const closedPnl = closedRes.data.reduce((sum, t) => sum + (t.pnl || 0), 0);
      
      setStats({
        totalInvested: invested,
        currentValue: currentValue,
        totalPnl: closedPnl + (currentValue - invested),
        totalPnlPercent: invested > 0 ? ((currentValue - invested) / invested * 100) : 0
      });
      
      if (onTradeUpdate) {
        onTradeUpdate({ open: openRes.data.length, closed: closedRes.data.length });
      }
    } catch (error) {
      console.error('Error fetching trades:', error);
    }
    setLoading(false);
  }, [API_URL, onTradeUpdate]);

  // Update trade prices from API
  const updateTradePrices = useCallback(async () => {
    if (openTrades.length === 0) return;
    
    for (const trade of openTrades) {
      try {
        const response = await axios.get(`${API_URL}/tokens/${trade.token_address}`);
        const currentPrice = response.data.price_usd;
        
        if (currentPrice && currentPrice !== trade.price_current) {
          await axios.put(`${API_URL}/trades/${trade.id}/update-price`, null, {
            params: { current_price: currentPrice }
          });
        }
      } catch (error) {
        // Token might not be found
      }
    }
    fetchTrades();
  }, [API_URL, openTrades, fetchTrades]);

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(() => {
      fetchTrades();
      updateTradePrices();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchTrades, updateTradePrices]);

  const closeTrade = async (tradeId, currentPrice, reason = 'MANUAL') => {
    try {
      const response = await axios.put(`${API_URL}/trades/${tradeId}/close`, null, {
        params: { exit_price: currentPrice, reason }
      });
      
      const pnl = response.data.pnl_percent;
      toast.success(
        `Trade Closed ${pnl >= 0 ? '📈' : '📉'}`,
        {
          description: `P&L: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}% (${response.data.pnl >= 0 ? '+' : ''}${response.data.pnl.toFixed(6)} SOL)`
        }
      );
      fetchTrades();
    } catch (error) {
      toast.error('Failed to close trade');
    }
  };

  const formatPrice = (price) => {
    if (!price) return '$0';
    if (price < 0.00001) return `$${price.toExponential(2)}`;
    if (price < 0.01) return `$${price.toFixed(6)}`;
    return `$${price.toFixed(4)}`;
  };

  const calculateProgress = (entry, current, takeProfit, stopLoss) => {
    const range = takeProfit - stopLoss;
    const position = current - stopLoss;
    return Math.max(0, Math.min(100, (position / range) * 100));
  };

  const getPnlColor = (pnl) => pnl >= 0 ? 'text-neon-green' : 'text-neon-red';

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
        <CardContent className="p-3">
          {openTrades.length === 0 ? (
            <div className="text-center py-6 text-muted-foreground text-sm">
              No active trades
            </div>
          ) : (
            <ScrollArea className="h-[300px]">
              <div className="space-y-2">
                {openTrades.map((trade, index) => {
                  const pnlPercent = ((trade.price_current / trade.price_entry) - 1) * 100;
                  const pnlSol = trade.amount_sol * (pnlPercent / 100);
                  
                  return (
                    <div 
                      key={trade.id} 
                      className="p-3 bg-[#050505] rounded-sm border border-[#1E293B] hover:border-neon-violet/30 transition-colors"
                      data-testid={`trade-compact-${index}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-xs font-bold">
                            {trade.token_symbol.slice(0, 2)}
                          </div>
                          <div>
                            <div className="font-semibold text-sm">{trade.token_symbol}</div>
                            <div className="text-xs text-muted-foreground">
                              {trade.amount_sol.toFixed(4)} SOL
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-neon-red hover:bg-neon-red/10"
                          onClick={() => closeTrade(trade.id, trade.price_current)}
                          data-testid={`close-trade-${index}`}
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                        <div>
                          <span className="text-muted-foreground">Entry: </span>
                          <span className="font-mono">{formatPrice(trade.price_entry)}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Now: </span>
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
                          {trade.paper_trade ? 'Paper' : 'Live'}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </CardContent>
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
            <div className="text-xs text-muted-foreground mb-1">Total Invested</div>
            <div className="font-mono font-bold text-neon-cyan">
              {stats.totalInvested.toFixed(4)} SOL
            </div>
            <div className="text-xs text-muted-foreground">
              ≈ ${(stats.totalInvested * solPrice).toFixed(2)}
            </div>
          </div>
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="text-xs text-muted-foreground mb-1">Current Value</div>
            <div className="font-mono font-bold">
              {stats.currentValue.toFixed(4)} SOL
            </div>
            <div className="text-xs text-muted-foreground">
              ≈ ${(stats.currentValue * solPrice).toFixed(2)}
            </div>
          </div>
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="text-xs text-muted-foreground mb-1">Total P&L</div>
            <div className={`font-mono font-bold ${getPnlColor(stats.totalPnl)}`}>
              {stats.totalPnl >= 0 ? '+' : ''}{stats.totalPnl.toFixed(4)} SOL
            </div>
            <div className={`text-xs ${getPnlColor(stats.totalPnl)}`}>
              {stats.totalPnlPercent >= 0 ? '+' : ''}{stats.totalPnlPercent.toFixed(2)}%
            </div>
          </div>
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="text-xs text-muted-foreground mb-1">Net Result</div>
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
              Active ({openTrades.length})
            </TabsTrigger>
            <TabsTrigger value="closed" className="data-[state=active]:bg-[#1E293B]">
              Closed ({closedTrades.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="open" className="mt-0">
            <ScrollArea className="h-[400px]">
              {openTrades.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
                  <BarChart3 className="w-8 h-8 mb-2" />
                  <p>No active trades</p>
                </div>
              ) : (
                <div className="divide-y divide-[#1E293B]">
                  {/* Table Header */}
                  <div className="grid grid-cols-7 gap-2 px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground bg-[#050505]">
                    <div>Token</div>
                    <div className="text-right">Entry</div>
                    <div className="text-right">Current</div>
                    <div className="text-right">Amount</div>
                    <div className="text-right">P&L</div>
                    <div className="text-right">ROI</div>
                    <div className="text-center">Action</div>
                  </div>
                  
                  {openTrades.map((trade, index) => {
                    const pnlPercent = ((trade.price_current / trade.price_entry) - 1) * 100;
                    const pnlSol = trade.amount_sol * (pnlPercent / 100);
                    
                    return (
                      <div 
                        key={trade.id}
                        className="grid grid-cols-7 gap-2 px-4 py-3 hover:bg-white/5 transition-colors items-center"
                        data-testid={`trade-row-${index}`}
                      >
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-xs font-bold">
                            {trade.token_symbol.slice(0, 2)}
                          </div>
                          <div>
                            <div className="font-semibold text-sm">{trade.token_symbol}</div>
                            <Badge variant="outline" className={`text-xs ${trade.paper_trade ? 'border-neon-cyan/30 text-neon-cyan' : 'border-neon-green/30 text-neon-green'}`}>
                              {trade.paper_trade ? 'Paper' : 'Live'}
                            </Badge>
                          </div>
                        </div>
                        <div className="text-right font-mono text-sm">
                          {formatPrice(trade.price_entry)}
                        </div>
                        <div className="text-right font-mono text-sm">
                          {formatPrice(trade.price_current)}
                        </div>
                        <div className="text-right font-mono text-sm">
                          {trade.amount_sol.toFixed(4)} SOL
                        </div>
                        <div className={`text-right font-mono text-sm font-bold ${getPnlColor(pnlSol)}`}>
                          {pnlSol >= 0 ? '+' : ''}{pnlSol.toFixed(6)} SOL
                        </div>
                        <div className={`text-right font-mono text-sm font-bold ${getPnlColor(pnlPercent)}`}>
                          {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                        </div>
                        <div className="flex justify-center">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-neon-red hover:bg-neon-red/10"
                            onClick={() => closeTrade(trade.id, trade.price_current)}
                          >
                            Close
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          <TabsContent value="closed" className="mt-0">
            <ScrollArea className="h-[400px]">
              {closedTrades.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
                  <CheckCircle className="w-8 h-8 mb-2" />
                  <p>No closed trades yet</p>
                </div>
              ) : (
                <div className="divide-y divide-[#1E293B]">
                  {closedTrades.map((trade, index) => (
                    <div 
                      key={trade.id}
                      className="grid grid-cols-7 gap-2 px-4 py-3 hover:bg-white/5 transition-colors items-center"
                    >
                      <div className="flex items-center gap-2">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${trade.pnl >= 0 ? 'bg-neon-green/20' : 'bg-neon-red/20'}`}>
                          {trade.pnl >= 0 ? <TrendingUp className="w-4 h-4 text-neon-green" /> : <TrendingDown className="w-4 h-4 text-neon-red" />}
                        </div>
                        <div>
                          <div className="font-semibold text-sm">{trade.token_symbol}</div>
                          <div className="text-xs text-muted-foreground">{trade.close_reason}</div>
                        </div>
                      </div>
                      <div className="text-right font-mono text-sm">
                        {formatPrice(trade.price_entry)}
                      </div>
                      <div className="text-right font-mono text-sm">
                        {formatPrice(trade.price_exit)}
                      </div>
                      <div className="text-right font-mono text-sm">
                        {trade.amount_sol.toFixed(4)} SOL
                      </div>
                      <div className={`text-right font-mono text-sm font-bold ${getPnlColor(trade.pnl)}`}>
                        {trade.pnl >= 0 ? '+' : ''}{trade.pnl?.toFixed(6)} SOL
                      </div>
                      <div className={`text-right font-mono text-sm font-bold ${getPnlColor(trade.pnl_percent)}`}>
                        {trade.pnl_percent >= 0 ? '+' : ''}{trade.pnl_percent?.toFixed(2)}%
                      </div>
                      <div className="flex justify-center">
                        {trade.tx_signature && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7"
                            onClick={() => window.open(`https://solscan.io/tx/${trade.tx_signature}`, '_blank')}
                          >
                            <ExternalLink className="w-3 h-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

export default LiveTradesPanel;
