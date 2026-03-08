import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { useWallet } from '@solana/wallet-adapter-react';
import { 
  X, 
  TrendingUp, 
  TrendingDown, 
  Shield, 
  AlertTriangle,
  DollarSign,
  Target,
  Percent,
  Zap,
  Check,
  Activity,
  ExternalLink,
  Loader2
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Switch } from './ui/switch';
import { Progress } from './ui/progress';
import { toast } from 'sonner';
import { buyToken, sellToken, SOL_MINT } from '../services/jupiterService';

const TradeModal = ({ token, opportunity = null, onClose, onSuccess }) => {
  const { API_URL } = useApp();
  const { connected, publicKey, signTransaction, wallet } = useWallet();
  
  const [botSettings, setBotSettings] = useState(null);
  const [tradeType, setTradeType] = useState('BUY');
  const [amountSOL, setAmountSOL] = useState(0.1);
  const [takeProfitPercent, setTakeProfitPercent] = useState(100);
  const [stopLossPercent, setStopLossPercent] = useState(25);
  const [trailingStopEnabled, setTrailingStopEnabled] = useState(false);
  const [trailingStopPercent, setTrailingStopPercent] = useState(10);
  const [usePaperMode, setUsePaperMode] = useState(true);
  const [loading, setLoading] = useState(false);
  const [swapStatus, setSwapStatus] = useState(null);
  const [txSignature, setTxSignature] = useState(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await axios.get(`${API_URL}/bot/settings`);
        const settings = response.data;
        setBotSettings(settings);
        setAmountSOL(settings.total_budget_sol * (settings.max_trade_percent / 100));
        setTakeProfitPercent(settings.take_profit_percent);
        setStopLossPercent(settings.stop_loss_percent);
        setTrailingStopEnabled(settings.trailing_stop_enabled);
        setTrailingStopPercent(settings.trailing_stop_percent);
        setUsePaperMode(settings.paper_mode);
      } catch (error) {
        console.error('Error fetching settings:', error);
      }
    };
    fetchSettings();
  }, [API_URL]);

  const formatPrice = (price) => {
    if (!price) return '0';
    if (price < 0.00001) return price.toExponential(2);
    if (price < 0.01) return price.toFixed(6);
    return price.toFixed(4);
  };

  const calculatePrices = () => {
    const entryPrice = token.price_usd;
    const takeProfitPrice = entryPrice * (1 + takeProfitPercent / 100);
    const stopLossPrice = entryPrice * (1 - stopLossPercent / 100);
    
    return { takeProfitPrice, stopLossPrice };
  };

  const { takeProfitPrice, stopLossPrice } = calculatePrices();
  const maxTradeAmount = botSettings ? botSettings.total_budget_sol * (botSettings.max_trade_percent / 100) : 0.1;

  // Handle swap status updates
  const handleSwapStatus = (status, message) => {
    setSwapStatus({ status, message });
    console.log(`🔄 Swap Status: ${status} - ${message}`);
  };

  // Execute live trade using Jupiter
  const executeLiveTrade = async () => {
    if (!wallet?.adapter) {
      toast.error('Wallet not connected properly');
      return null;
    }

    try {
      let result;
      
      if (tradeType === 'BUY') {
        // Buy token with SOL
        result = await buyToken(
          wallet.adapter,
          token.address,
          amountSOL,
          100, // 1% slippage
          handleSwapStatus
        );
      } else {
        // Sell token for SOL
        // Note: For selling, we need the token amount, not SOL amount
        // This would require fetching the user's token balance
        toast.error('Sell functionality requires token balance check');
        return null;
      }

      if (result.success) {
        setTxSignature(result.signature);
        return result;
      } else {
        if (result.cancelled) {
          toast.info('Transaction cancelled');
        } else {
          toast.error('Swap failed', { description: result.error });
        }
        return null;
      }
    } catch (error) {
      console.error('Live trade error:', error);
      toast.error('Trade execution failed', { description: error.message });
      return null;
    }
  };

  const handleSubmit = async () => {
    if (!usePaperMode && !connected) {
      toast.error('Please connect your wallet for live trading');
      return;
    }

    setLoading(true);
    setSwapStatus(null);
    setTxSignature(null);

    try {
      let txSig = null;

      // Execute live trade via Jupiter if not paper mode
      if (!usePaperMode) {
        const liveResult = await executeLiveTrade();
        if (!liveResult) {
          setLoading(false);
          return;
        }
        txSig = liveResult.signature;
      }

      // Record trade in database
      const tradeData = {
        token_address: token.address,
        token_symbol: token.symbol,
        token_name: token.name,
        pair_address: token.pair_address,
        trade_type: tradeType,
        amount_sol: amountSOL,
        price_entry: token.price_usd,
        take_profit_percent: takeProfitPercent,
        stop_loss_percent: stopLossPercent,
        trailing_stop_percent: trailingStopEnabled ? trailingStopPercent : null,
        paper_trade: usePaperMode,
        auto_trade: false,
        wallet_address: publicKey?.toString() || null,
        tx_signature: txSig
      };

      await axios.post(`${API_URL}/trades`, tradeData);
      
      if (usePaperMode) {
        toast.success(
          `Paper ${tradeType} order placed!`,
          {
            description: `${token.symbol} | ${amountSOL.toFixed(4)} SOL | TP: +${takeProfitPercent}% | SL: -${stopLossPercent}%`
          }
        );
      } else {
        toast.success(
          `Live ${tradeType} executed!`,
          {
            description: `${token.symbol} | ${amountSOL.toFixed(4)} SOL`,
            action: txSig ? {
              label: 'View on Solscan',
              onClick: () => window.open(`https://solscan.io/tx/${txSig}`, '_blank')
            } : undefined
          }
        );
      }
      
      onSuccess && onSuccess();
      onClose();
    } catch (error) {
      console.error('Error placing trade:', error);
      toast.error('Failed to place trade', {
        description: error.response?.data?.detail || 'Please try again'
      });
    }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" data-testid="trade-modal">
      <div className="bg-[#0A0A0A] border border-[#1E293B] rounded-sm w-full max-w-lg animate-in">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1E293B]">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-sm font-bold">
                {token.symbol.slice(0, 2)}
              </div>
              {token.signal_strength && (
                <div className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center ${
                  token.signal_strength === 'STRONG' ? 'bg-neon-green' : 
                  token.signal_strength === 'MEDIUM' ? 'bg-yellow-500' : 'bg-gray-500'
                }`}>
                  <Activity className="w-2.5 h-2.5 text-black" />
                </div>
              )}
            </div>
            <div>
              <h2 className="font-heading font-bold text-lg flex items-center gap-2">
                {token.symbol}
                {opportunity && (
                  <Badge className="bg-neon-green/20 text-neon-green border-none text-xs">
                    {opportunity.confidence.toFixed(0)}% Confidence
                  </Badge>
                )}
              </h2>
              <p className="text-sm text-muted-foreground">{token.name}</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} data-testid="close-modal">
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Token Stats */}
        <div className="p-4 border-b border-[#1E293B]">
          <div className="grid grid-cols-5 gap-2 text-center">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Price</div>
              <div className="font-mono text-sm">${formatPrice(token.price_usd)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">5m</div>
              <div className={`font-mono text-sm ${(token.price_change_5m || 0) >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                {(token.price_change_5m || 0) >= 0 ? '+' : ''}{(token.price_change_5m || 0).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Liquidity</div>
              <div className="font-mono text-sm">
                ${token.liquidity >= 1000 ? `${(token.liquidity / 1000).toFixed(1)}K` : token.liquidity?.toFixed(0)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">B/S Ratio</div>
              <div className={`font-mono text-sm ${token.buy_sell_ratio >= 1 ? 'text-neon-green' : 'text-neon-red'}`}>
                {token.buy_sell_ratio?.toFixed(1)}x
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Risk</div>
              <Badge 
                variant="outline" 
                className={`text-xs ${
                  token.risk_analysis?.risk_score < 40 
                    ? 'border-neon-green/30 text-neon-green' 
                    : token.risk_analysis?.risk_score < 70 
                    ? 'border-yellow-500/30 text-yellow-500' 
                    : 'border-neon-red/30 text-neon-red'
                }`}
              >
                {token.risk_analysis?.risk_score || 50}
              </Badge>
            </div>
          </div>

          {/* Momentum Bar */}
          {token.momentum_score !== undefined && (
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground">Momentum</span>
                <span className="font-mono">{token.momentum_score.toFixed(0)}/100</span>
              </div>
              <Progress value={token.momentum_score} className="h-1.5" />
            </div>
          )}
        </div>

        {/* Trade Form */}
        <div className="p-4 space-y-4">
          {/* Trade Type */}
          <div className="flex gap-2">
            <Button
              variant={tradeType === 'BUY' ? 'default' : 'outline'}
              className={`flex-1 ${tradeType === 'BUY' ? 'bg-neon-green text-black hover:bg-neon-green/90' : ''}`}
              onClick={() => setTradeType('BUY')}
              data-testid="buy-button"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Buy
            </Button>
            <Button
              variant={tradeType === 'SELL' ? 'default' : 'outline'}
              className={`flex-1 ${tradeType === 'SELL' ? 'bg-neon-red text-white hover:bg-neon-red/90' : ''}`}
              onClick={() => setTradeType('SELL')}
              data-testid="sell-button"
            >
              <TrendingDown className="w-4 h-4 mr-2" />
              Sell
            </Button>
          </div>

          {/* Amount */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-xs uppercase tracking-widest text-muted-foreground">
                Amount (SOL)
              </Label>
              <span className="text-xs text-muted-foreground">
                Max: {maxTradeAmount.toFixed(4)} SOL
              </span>
            </div>
            <Input
              type="number"
              step="0.01"
              min="0.01"
              max={maxTradeAmount}
              value={amountSOL}
              onChange={(e) => setAmountSOL(Math.min(parseFloat(e.target.value) || 0, maxTradeAmount))}
              className="bg-[#0F172A] border-[#1E293B] font-mono"
              data-testid="amount-input"
            />
            <div className="flex gap-2 mt-2">
              {[0.25, 0.5, 0.75, 1].map((pct) => (
                <Button
                  key={pct}
                  variant="outline"
                  size="sm"
                  className="flex-1 text-xs"
                  onClick={() => setAmountSOL(maxTradeAmount * pct)}
                >
                  {pct * 100}%
                </Button>
              ))}
            </div>
          </div>

          {/* Take Profit */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-xs uppercase tracking-widest text-muted-foreground">
                Take Profit
              </Label>
              <span className="font-mono text-neon-green">+{takeProfitPercent}%</span>
            </div>
            <Slider
              value={[takeProfitPercent]}
              onValueChange={(value) => setTakeProfitPercent(value[0])}
              min={20}
              max={500}
              step={10}
              data-testid="take-profit-slider"
            />
            <div className="text-xs text-muted-foreground mt-1">
              Target: ${formatPrice(takeProfitPrice)}
            </div>
          </div>

          {/* Stop Loss */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-xs uppercase tracking-widest text-muted-foreground">
                Stop Loss
              </Label>
              <span className="font-mono text-neon-red">-{stopLossPercent}%</span>
            </div>
            <Slider
              value={[stopLossPercent]}
              onValueChange={(value) => setStopLossPercent(value[0])}
              min={5}
              max={50}
              step={5}
              data-testid="stop-loss-slider"
            />
            <div className="text-xs text-muted-foreground mt-1">
              Trigger: ${formatPrice(stopLossPrice)}
            </div>
          </div>

          {/* Trailing Stop */}
          <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 text-yellow-500" />
              <div>
                <span className="text-sm">Trailing Stop</span>
                {trailingStopEnabled && (
                  <span className="ml-2 text-xs text-yellow-500">-{trailingStopPercent}%</span>
                )}
              </div>
            </div>
            <Switch 
              checked={trailingStopEnabled} 
              onCheckedChange={setTrailingStopEnabled}
            />
          </div>

          {trailingStopEnabled && (
            <Slider
              value={[trailingStopPercent]}
              onValueChange={(value) => setTrailingStopPercent(value[0])}
              min={5}
              max={30}
              step={1}
            />
          )}

          {/* Paper Mode Toggle */}
          <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-neon-cyan" />
              <span className="text-sm">Paper Trading Mode</span>
            </div>
            <Switch 
              checked={usePaperMode} 
              onCheckedChange={setUsePaperMode}
              data-testid="paper-mode-switch"
            />
          </div>

          {/* Warning for Live Trading */}
          {!usePaperMode && (
            <div className="flex items-start gap-2 p-3 bg-neon-red/10 border border-neon-red/30 rounded-sm">
              <AlertTriangle className="w-4 h-4 text-neon-red mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <span className="font-semibold text-neon-red">Live Trading:</span>{' '}
                <span className="text-muted-foreground">
                  Real funds will be used. Ensure you understand the risks.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#1E293B]">
          <Button
            className={`w-full py-6 font-semibold ${
              tradeType === 'BUY' 
                ? 'bg-neon-green text-black hover:bg-neon-green/90' 
                : 'bg-neon-red text-white hover:bg-neon-red/90'
            }`}
            onClick={handleSubmit}
            disabled={loading || (!usePaperMode && !connected)}
            data-testid="confirm-trade"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                Processing...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Check className="w-5 h-5" />
                {tradeType} {token.symbol} ({usePaperMode ? 'Paper' : 'Live'})
              </span>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default TradeModal;
