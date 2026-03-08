import React, { useState, useEffect, useCallback } from 'react';
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
  RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Progress } from './ui/progress';

const ActiveTrades = ({ compact = false }) => {
  const { API_URL, solPrice } = useApp();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchTrades = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/trades`, {
        params: { status: 'OPEN' }
      });
      setTrades(response.data);
    } catch (error) {
      console.error('Error fetching trades:', error);
    }
    setLoading(false);
  }, [API_URL]);

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 10000);
    return () => clearInterval(interval);
  }, [fetchTrades]);

  const closeTrade = async (tradeId, exitPrice) => {
    try {
      await axios.put(`${API_URL}/trades/${tradeId}/close`, null, {
        params: { exit_price: exitPrice }
      });
      fetchTrades();
    } catch (error) {
      console.error('Error closing trade:', error);
    }
  };

  const formatNumber = (num) => {
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`;
    if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`;
    return `$${num.toFixed(2)}`;
  };

  const formatPrice = (price) => {
    if (price < 0.00001) return price.toExponential(2);
    if (price < 0.01) return price.toFixed(6);
    return price.toFixed(4);
  };

  const calculateProgress = (entry, current, takeProfit, stopLoss) => {
    const range = takeProfit - stopLoss;
    const position = current - stopLoss;
    return Math.max(0, Math.min(100, (position / range) * 100));
  };

  if (compact) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B] h-full" data-testid="active-trades-compact">
        <CardHeader className="border-b border-[#1E293B]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-neon-violet" />
              <CardTitle className="font-heading">Active Trades</CardTitle>
              <Badge variant="outline" className="border-neon-violet/30 text-neon-violet">
                {trades.length}
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
        <CardContent className="p-4">
          {trades.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
              <BarChart3 className="w-8 h-8 mb-2" />
              <p>No active trades</p>
            </div>
          ) : (
            <div className="space-y-3">
              {trades.slice(0, 5).map((trade, index) => (
                <div 
                  key={trade.id} 
                  className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]"
                  data-testid={`trade-compact-${index}`}
                >
                  <div className="flex items-center gap-3">
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
                  <div className="text-right">
                    <div className={`font-mono text-sm ${trade.pnl_percent >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                      {trade.pnl_percent >= 0 ? '+' : ''}{trade.pnl_percent.toFixed(1)}%
                    </div>
                    <Badge variant="outline" className={`text-xs ${trade.paper_trade ? 'border-neon-cyan/30 text-neon-cyan' : 'border-neon-green/30 text-neon-green'}`}>
                      {trade.paper_trade ? 'Paper' : 'Live'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="active-trades">
      <CardHeader className="border-b border-[#1E293B]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-neon-violet" />
            <CardTitle className="font-heading">Active Trades</CardTitle>
            <Badge variant="outline" className="border-neon-violet/30 text-neon-violet">
              {trades.length} open
            </Badge>
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
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[500px]">
          {trades.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
              <BarChart3 className="w-8 h-8 mb-2" />
              <p>No active trades</p>
              <p className="text-sm">Start trading from the Token Scanner</p>
            </div>
          ) : (
            <div className="divide-y divide-[#1E293B]">
              {trades.map((trade, index) => (
                <div 
                  key={trade.id} 
                  className="p-4 hover:bg-white/5 transition-colors"
                  data-testid={`trade-row-${index}`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-sm font-bold">
                        {trade.token_symbol.slice(0, 2)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{trade.token_symbol}</span>
                          <Badge variant="outline" className={`text-xs ${trade.paper_trade ? 'border-neon-cyan/30 text-neon-cyan' : 'border-neon-green/30 text-neon-green'}`}>
                            {trade.paper_trade ? 'Paper' : 'Live'}
                          </Badge>
                          <Badge variant="outline" className="text-xs border-neon-violet/30 text-neon-violet">
                            {trade.trade_type}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {trade.token_name}
                        </div>
                      </div>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon"
                      className="text-muted-foreground hover:text-neon-red"
                      onClick={() => closeTrade(trade.id, trade.price_current)}
                      data-testid={`close-trade-${index}`}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>

                  {/* Trade Stats */}
                  <div className="grid grid-cols-4 gap-4 mb-3">
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Entry</div>
                      <div className="font-mono text-sm">${formatPrice(trade.price_entry)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Current</div>
                      <div className="font-mono text-sm">${formatPrice(trade.price_current)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Amount</div>
                      <div className="font-mono text-sm">{trade.amount_sol.toFixed(4)} SOL</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">P&L</div>
                      <div className={`font-mono text-sm font-bold ${trade.pnl_percent >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                        {trade.pnl_percent >= 0 ? '+' : ''}{trade.pnl_percent.toFixed(2)}%
                      </div>
                    </div>
                  </div>

                  {/* Progress to TP/SL */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 text-neon-red" />
                        SL: ${formatPrice(trade.stop_loss)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Target className="w-3 h-3 text-neon-green" />
                        TP: ${formatPrice(trade.take_profit)}
                      </span>
                    </div>
                    <div className="relative">
                      <Progress 
                        value={calculateProgress(trade.price_entry, trade.price_current, trade.take_profit, trade.stop_loss)} 
                        className="h-2"
                      />
                      <div 
                        className="absolute top-0 h-full w-0.5 bg-white"
                        style={{ 
                          left: `${calculateProgress(trade.price_entry, trade.price_entry, trade.take_profit, trade.stop_loss)}%` 
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default ActiveTrades;
