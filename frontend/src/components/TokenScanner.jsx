import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { 
  Search, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  Shield, 
  AlertTriangle,
  Clock,
  Users,
  Droplet,
  BarChart2,
  ExternalLink,
  Zap
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Progress } from './ui/progress';
import TradeModal from './TradeModal';

const TokenScanner = () => {
  const { API_URL, solPrice } = useApp();
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedToken, setSelectedToken] = useState(null);
  const [showTradeModal, setShowTradeModal] = useState(false);

  const fetchTokens = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_URL}/tokens/scan`, {
        params: { limit: 30 }
      });
      setTokens(response.data);
    } catch (error) {
      console.error('Error fetching tokens:', error);
    }
    setLoading(false);
  }, [API_URL]);

  useEffect(() => {
    fetchTokens();
    const interval = setInterval(fetchTokens, 30000);
    return () => clearInterval(interval);
  }, [fetchTokens]);

  const filteredTokens = tokens.filter(token => 
    token.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    token.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
    token.address.toLowerCase().includes(searchTerm.toLowerCase())
  );

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

  const getRiskColor = (score) => {
    if (score < 40) return 'text-neon-green';
    if (score < 70) return 'text-yellow-500';
    return 'text-neon-red';
  };

  const getRiskBadge = (risk) => {
    const colors = {
      LOW: 'bg-neon-green/20 text-neon-green border-neon-green/30',
      MEDIUM: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
      HIGH: 'bg-neon-red/20 text-neon-red border-neon-red/30'
    };
    return colors[risk] || colors.MEDIUM;
  };

  const handleTokenClick = (token) => {
    setSelectedToken(token);
    setShowTradeModal(true);
  };

  return (
    <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="token-scanner">
      <CardHeader className="border-b border-[#1E293B]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-neon-cyan" />
            <CardTitle className="font-heading">Token Scanner</CardTitle>
            <Badge variant="outline" className="border-neon-cyan/30 text-neon-cyan">
              {tokens.length} tokens
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search tokens..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 w-64 bg-[#0F172A] border-[#1E293B]"
                data-testid="token-search"
              />
            </div>
            <Button 
              variant="outline" 
              size="icon" 
              onClick={fetchTokens}
              disabled={loading}
              data-testid="refresh-tokens"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[600px]">
          <div className="divide-y divide-[#1E293B]">
            {/* Header Row */}
            <div className="grid grid-cols-12 gap-2 px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground bg-[#050505] sticky top-0 z-10">
              <div className="col-span-3">Token</div>
              <div className="col-span-2 text-right">Price</div>
              <div className="col-span-1 text-right">24h</div>
              <div className="col-span-2 text-right">Liquidity</div>
              <div className="col-span-1 text-right">Volume</div>
              <div className="col-span-1 text-right">B/S Ratio</div>
              <div className="col-span-2 text-right">Risk</div>
            </div>

            {/* Token Rows */}
            {loading && tokens.length === 0 ? (
              <div className="flex items-center justify-center h-40">
                <RefreshCw className="w-6 h-6 animate-spin text-neon-cyan" />
              </div>
            ) : filteredTokens.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
                <Search className="w-8 h-8 mb-2" />
                <p>No tokens found</p>
              </div>
            ) : (
              filteredTokens.map((token, index) => (
                <div
                  key={token.address}
                  className="grid grid-cols-12 gap-2 px-4 py-3 hover:bg-white/5 cursor-pointer transition-colors group"
                  onClick={() => handleTokenClick(token)}
                  data-testid={`token-row-${index}`}
                >
                  {/* Token Info */}
                  <div className="col-span-3 flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-xs font-bold">
                      {token.symbol.slice(0, 2)}
                    </div>
                    <div className="overflow-hidden">
                      <div className="font-semibold truncate group-hover:text-neon-cyan transition-colors">
                        {token.symbol}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {token.name}
                      </div>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="col-span-2 text-right font-mono">
                    ${formatPrice(token.price_usd)}
                  </div>

                  {/* 24h Change */}
                  <div className={`col-span-1 text-right font-mono flex items-center justify-end gap-1 ${token.price_change_24h >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                    {token.price_change_24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {Math.abs(token.price_change_24h).toFixed(1)}%
                  </div>

                  {/* Liquidity */}
                  <div className="col-span-2 text-right font-mono text-muted-foreground">
                    {formatNumber(token.liquidity)}
                  </div>

                  {/* Volume */}
                  <div className="col-span-1 text-right font-mono text-muted-foreground">
                    {formatNumber(token.volume_24h)}
                  </div>

                  {/* Buy/Sell Ratio */}
                  <div className={`col-span-1 text-right font-mono ${token.buy_sell_ratio >= 1 ? 'text-neon-green' : 'text-neon-red'}`}>
                    {token.buy_sell_ratio.toFixed(2)}x
                  </div>

                  {/* Risk Score */}
                  <div className="col-span-2 flex items-center justify-end gap-2">
                    {token.risk_analysis && (
                      <>
                        <div className="w-16">
                          <Progress 
                            value={100 - token.risk_analysis.risk_score} 
                            className="h-1.5"
                          />
                        </div>
                        <Badge 
                          variant="outline" 
                          className={`text-xs ${getRiskBadge(token.risk_analysis.honeypot_risk)}`}
                        >
                          {token.risk_analysis.risk_score}
                        </Badge>
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>

      {/* Trade Modal */}
      {showTradeModal && selectedToken && (
        <TradeModal
          token={selectedToken}
          onClose={() => {
            setShowTradeModal(false);
            setSelectedToken(null);
          }}
        />
      )}
    </Card>
  );
};

export default TokenScanner;
