import React, { useState } from 'react';
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
  ExternalLink
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Switch } from './ui/switch';
import { Progress } from './ui/progress';
import { toast } from 'sonner';

const TradeModal = ({ token, opportunity = null, onClose }) => {
  const { API_URL, settings, paperMode, solPrice } = useApp();
  const { connected, publicKey } = useWallet();
  
  const [tradeType, setTradeType] = useState('BUY');
  const [amountSOL, setAmountSOL] = useState(settings?.stake_per_trade || 0.1);
  const [takeProfitPercent, setTakeProfitPercent] = useState(settings?.take_profit_percent || 100);
  const [stopLossPercent, setStopLossPercent] = useState(settings?.stop_loss_percent || 30);
  const [usePaperMode, setUsePaperMode] = useState(paperMode);
  const [loading, setLoading] = useState(false);

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
    const potentialProfit = amountSOL * solPrice * (takeProfitPercent / 100);
    const potentialLoss = amountSOL * solPrice * (stopLossPercent / 100);
    
    return { takeProfitPrice, stopLossPrice, potentialProfit, potentialLoss };
  };

  const { takeProfitPrice, stopLossPrice, potentialProfit, potentialLoss } = calculatePrices();

  const handleSubmit = async () => {
    if (!usePaperMode && !connected) {
      toast.error('Please connect your wallet for live trading');
      return;
    }

    setLoading(true);
    try {
      const tradeData = {
        token_address: token.address,
        token_symbol: token.symbol,
        token_name: token.name,
        trade_type: tradeType,
        amount_sol: amountSOL,
        price_entry: token.price_usd,
        take_profit_percent: takeProfitPercent,
        stop_loss_percent: stopLossPercent,
        paper_trade: usePaperMode,
        wallet_address: publicKey?.toString() || null
      };

      await axios.post(`${API_URL}/trades`, tradeData);
      
      toast.success(
        `${usePaperMode ? 'Paper' : 'Live'} ${tradeType} order placed for ${token.symbol}`,
        {
          description: `Amount: ${amountSOL} SOL | TP: +${takeProfitPercent}% | SL: -${stopLossPercent}%`
        }
      );
      
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
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-sm font-bold">
              {token.symbol.slice(0, 2)}
            </div>
            <div>
              <h2 className="font-heading font-bold text-lg">{token.symbol}</h2>
              <p className="text-sm text-muted-foreground">{token.name}</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} data-testid="close-modal">
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Token Stats */}
        <div className="p-4 border-b border-[#1E293B]">
          <div className="grid grid-cols-4 gap-3">
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">Price</div>
              <div className="font-mono font-semibold">${formatPrice(token.price_usd)}</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">24h</div>
              <div className={`font-mono font-semibold ${token.price_change_24h >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                {token.price_change_24h >= 0 ? '+' : ''}{token.price_change_24h?.toFixed(1)}%
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">Liquidity</div>
              <div className="font-mono font-semibold">
                ${token.liquidity >= 1000 ? `${(token.liquidity / 1000).toFixed(1)}K` : token.liquidity?.toFixed(0)}
              </div>
            </div>
            <div className="text-center">
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
            <Label className="text-xs uppercase tracking-widest text-muted-foreground">
              Amount (SOL)
            </Label>
            <div className="flex items-center gap-2 mt-2">
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={amountSOL}
                onChange={(e) => setAmountSOL(parseFloat(e.target.value) || 0)}
                className="bg-[#0F172A] border-[#1E293B] font-mono"
                data-testid="amount-input"
              />
              <div className="text-sm text-muted-foreground whitespace-nowrap">
                ≈ ${(amountSOL * solPrice).toFixed(2)}
              </div>
            </div>
            <div className="flex gap-2 mt-2">
              {[0.05, 0.1, 0.25, 0.5, 1].map((amount) => (
                <Button
                  key={amount}
                  variant="outline"
                  size="sm"
                  className="flex-1 text-xs"
                  onClick={() => setAmountSOL(amount)}
                >
                  {amount}
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
              min={10}
              max={500}
              step={10}
              className="mt-2"
              data-testid="take-profit-slider"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>Target: ${formatPrice(takeProfitPrice)}</span>
              <span className="text-neon-green">+${potentialProfit.toFixed(2)}</span>
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
              max={80}
              step={5}
              className="mt-2"
              data-testid="stop-loss-slider"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>Trigger: ${formatPrice(stopLossPrice)}</span>
              <span className="text-neon-red">-${potentialLoss.toFixed(2)}</span>
            </div>
          </div>

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
              <AlertTriangle className="w-4 h-4 text-neon-red mt-0.5" />
              <div className="text-sm">
                <span className="font-semibold text-neon-red">Live Trading:</span>{' '}
                <span className="text-muted-foreground">
                  Real funds will be used. Make sure you understand the risks.
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
                Confirm {tradeType} {usePaperMode ? '(Paper)' : '(Live)'}
              </span>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default TradeModal;
