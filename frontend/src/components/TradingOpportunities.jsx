import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { useWallet } from '@solana/wallet-adapter-react';
import { 
  Zap, 
  TrendingUp, 
  Shield, 
  AlertTriangle,
  RefreshCw,
  ArrowRight,
  Target,
  Clock,
  Activity,
  Check,
  X
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Progress } from './ui/progress';
import TradeModal from './TradeModal';
import { toast } from 'sonner';

const TradingOpportunities = ({ onSelectToken }) => {
  const { API_URL } = useApp();
  const { connected, publicKey } = useWallet();
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [botSettings, setBotSettings] = useState(null);

  const fetchOpportunities = useCallback(async () => {
    setLoading(true);
    try {
      const [oppRes, settingsRes] = await Promise.all([
        axios.get(`${API_URL}/opportunities`),
        axios.get(`${API_URL}/bot/settings`)
      ]);
      setOpportunities(oppRes.data);
      setBotSettings(settingsRes.data);
    } catch (error) {
      console.error('Error fetching opportunities:', error);
    }
    setLoading(false);
  }, [API_URL]);

  useEffect(() => {
    fetchOpportunities();
    const interval = setInterval(fetchOpportunities, 30000);
    return () => clearInterval(interval);
  }, [fetchOpportunities]);

  const getRiskColor = (level) => {
    const colors = {
      LOW: 'text-neon-green border-neon-green/30 bg-neon-green/10',
      MEDIUM: 'text-yellow-500 border-yellow-500/30 bg-yellow-500/10',
      HIGH: 'text-neon-red border-neon-red/30 bg-neon-red/10'
    };
    return colors[level] || colors.MEDIUM;
  };

  const getSignalColor = (signal) => {
    const colors = {
      STRONG: 'text-neon-green',
      MEDIUM: 'text-yellow-500',
      WEAK: 'text-muted-foreground',
      NONE: 'text-muted-foreground'
    };
    return colors[signal] || colors.NONE;
  };

  const handleTradeClick = (opportunity) => {
    setSelectedOpportunity(opportunity);
    setShowTradeModal(true);
  };

  const handleQuickTrade = async (opportunity) => {
    if (!botSettings) return;
    
    try {
      const tradeData = {
        token_address: opportunity.token.address,
        token_symbol: opportunity.token.symbol,
        token_name: opportunity.token.name,
        pair_address: opportunity.token.pair_address,
        trade_type: 'BUY',
        amount_sol: botSettings.total_budget_sol * (botSettings.max_trade_percent / 100),
        price_entry: opportunity.token.price_usd,
        take_profit_percent: botSettings.take_profit_percent,
        stop_loss_percent: botSettings.stop_loss_percent,
        trailing_stop_percent: botSettings.trailing_stop_enabled ? botSettings.trailing_stop_percent : null,
        paper_trade: botSettings.paper_mode,
        auto_trade: true,
        wallet_address: publicKey?.toString()
      };

      await axios.post(`${API_URL}/trades`, tradeData);
      
      toast.success(`${botSettings.paper_mode ? 'Paper' : 'Live'} trade opened!`, {
        description: `Bought ${opportunity.token.symbol} for ${tradeData.amount_sol.toFixed(4)} SOL`
      });
      
      fetchOpportunities();
    } catch (error) {
      toast.error('Failed to execute trade', {
        description: error.response?.data?.detail || 'Please try again'
      });
    }
  };

  const formatTime = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = (date.getTime() - now.getTime()) / 1000 / 60;
    
    if (diff < 0) return 'Expired';
    if (diff < 1) return 'Expires soon';
    return `${Math.floor(diff)}m left`;
  };

  return (
    <Card className="bg-[#0A0A0A] border-[#1E293B] h-full" data-testid="trading-opportunities">
      <CardHeader className="border-b border-[#1E293B]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-neon-green" />
            <CardTitle className="font-heading">Trading Opportunities</CardTitle>
            <Badge variant="outline" className="border-neon-green/30 text-neon-green animate-pulse">
              AI Signals
            </Badge>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={fetchOpportunities}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-4">
        {loading && opportunities.length === 0 ? (
          <div className="flex items-center justify-center h-60">
            <RefreshCw className="w-6 h-6 animate-spin text-neon-cyan" />
          </div>
        ) : opportunities.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-60 text-muted-foreground">
            <Zap className="w-12 h-12 mb-4 opacity-50" />
            <p className="font-semibold">Scanning for opportunities...</p>
            <p className="text-sm">High-quality signals will appear here</p>
          </div>
        ) : (
          <ScrollArea className="h-[400px]">
            <div className="space-y-3">
              {opportunities.map((opp, index) => (
                <div 
                  key={opp.id}
                  className="p-4 bg-[#050505] rounded-sm border border-[#1E293B] hover:border-neon-green/50 transition-all group"
                  data-testid={`opportunity-${index}`}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div 
                      className="flex items-center gap-3 cursor-pointer"
                      onClick={() => onSelectToken && onSelectToken(opp.token)}
                    >
                      <div className="relative">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-neon-green to-neon-cyan flex items-center justify-center text-sm font-bold">
                          {opp.token.symbol.slice(0, 2)}
                        </div>
                        <div className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center ${
                          opp.token.signal_strength === 'STRONG' ? 'bg-neon-green' : 
                          opp.token.signal_strength === 'MEDIUM' ? 'bg-yellow-500' : 'bg-gray-500'
                        }`}>
                          <Activity className="w-2.5 h-2.5 text-black" />
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold group-hover:text-neon-green transition-colors">
                            {opp.token.symbol}
                          </span>
                          <Badge className="bg-neon-green/20 text-neon-green border-none text-xs">
                            {opp.suggested_action}
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground truncate max-w-[180px]">
                          {opp.token.name}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button 
                        size="sm" 
                        variant="outline"
                        className="border-neon-cyan/30 text-neon-cyan hover:bg-neon-cyan/10"
                        onClick={() => handleTradeClick(opp)}
                      >
                        Custom
                      </Button>
                      <Button 
                        size="sm" 
                        className="bg-neon-green text-black hover:bg-neon-green/90"
                        onClick={() => handleQuickTrade(opp)}
                        disabled={!connected && !botSettings?.paper_mode}
                      >
                        Quick Trade
                        <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </div>
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-4 gap-2 mb-3">
                    <div className="text-center p-2 bg-[#0A0A0A] rounded-sm">
                      <div className="text-xs text-muted-foreground mb-0.5">Confidence</div>
                      <div className="font-mono font-semibold text-neon-cyan">
                        {opp.confidence.toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-center p-2 bg-[#0A0A0A] rounded-sm">
                      <div className="text-xs text-muted-foreground mb-0.5">Potential</div>
                      <div className="font-mono font-semibold text-neon-green">
                        +{opp.potential_profit.toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-center p-2 bg-[#0A0A0A] rounded-sm">
                      <div className="text-xs text-muted-foreground mb-0.5">Risk</div>
                      <Badge variant="outline" className={`text-xs ${getRiskColor(opp.risk_level)}`}>
                        {opp.risk_level}
                      </Badge>
                    </div>
                    <div className="text-center p-2 bg-[#0A0A0A] rounded-sm">
                      <div className="text-xs text-muted-foreground mb-0.5">Signal</div>
                      <span className={`text-xs font-semibold ${getSignalColor(opp.token.signal_strength)}`}>
                        {opp.token.signal_strength}
                      </span>
                    </div>
                  </div>

                  {/* Token Metrics */}
                  <div className="grid grid-cols-4 gap-2 mb-3 text-xs">
                    <div>
                      <span className="text-muted-foreground">Price:</span>
                      <span className="ml-1 font-mono">${opp.token.price_usd < 0.01 ? opp.token.price_usd.toExponential(2) : opp.token.price_usd.toFixed(4)}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">5m:</span>
                      <span className={`ml-1 font-mono ${opp.token.price_change_5m >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                        {opp.token.price_change_5m >= 0 ? '+' : ''}{opp.token.price_change_5m?.toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Liq:</span>
                      <span className="ml-1 font-mono">${(opp.token.liquidity / 1000).toFixed(1)}K</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">B/S:</span>
                      <span className={`ml-1 font-mono ${opp.token.buy_sell_ratio >= 1 ? 'text-neon-green' : 'text-neon-red'}`}>
                        {opp.token.buy_sell_ratio?.toFixed(1)}x
                      </span>
                    </div>
                  </div>

                  {/* Signal Reason */}
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-muted-foreground bg-[#0A0A0A] px-2 py-1 rounded flex-1 mr-2">
                      {opp.reason}
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      {formatTime(opp.expires_at)}
                    </div>
                  </div>

                  {/* Momentum Progress */}
                  <div className="mt-3">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-muted-foreground">Momentum Score</span>
                      <span className={`font-mono ${opp.token.momentum_score >= 70 ? 'text-neon-green' : opp.token.momentum_score >= 50 ? 'text-yellow-500' : 'text-muted-foreground'}`}>
                        {opp.token.momentum_score?.toFixed(0)}/100
                      </span>
                    </div>
                    <Progress value={opp.token.momentum_score || 0} className="h-1.5" />
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>

      {/* Trade Modal */}
      {showTradeModal && selectedOpportunity && (
        <TradeModal
          token={selectedOpportunity.token}
          opportunity={selectedOpportunity}
          onClose={() => {
            setShowTradeModal(false);
            setSelectedOpportunity(null);
          }}
          onSuccess={fetchOpportunities}
        />
      )}
    </Card>
  );
};

export default TradingOpportunities;
