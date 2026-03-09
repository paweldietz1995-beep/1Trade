import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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
  Activity,
  Filter,
  Check,
  X,
  Radio,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Progress } from './ui/progress';
import TradeModal from './TradeModal';

const PAGE_SIZE = 50;

const TokenScanner = ({ onSelectToken, showTradeButton = true }) => {
  const { t } = useTranslation();
  const { API_URL } = useApp();
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedToken, setSelectedToken] = useState(null);
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [filterPassed, setFilterPassed] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);

  const fetchTokens = useCallback(async () => {
    setLoading(true);
    try {
      // Request 500 tokens - NO LIMIT
      const response = await axios.get(`${API_URL}/tokens/scan`, {
        params: { limit: 500 }
      });
      setTokens(response.data);
      setCurrentPage(0); // Reset to first page on refresh
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

  const filteredTokens = tokens.filter(token => {
    const matchesSearch = token.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      token.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      token.address.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesFilter = filterPassed ? token.risk_analysis?.passed_filters : true;
    
    return matchesSearch && matchesFilter;
  });

  // Pagination
  const totalPages = Math.ceil(filteredTokens.length / PAGE_SIZE);
  const paginatedTokens = filteredTokens.slice(
    currentPage * PAGE_SIZE,
    (currentPage + 1) * PAGE_SIZE
  );

  const goToNextPage = () => {
    if (currentPage < totalPages - 1) {
      setCurrentPage(currentPage + 1);
    }
  };

  const goToPrevPage = () => {
    if (currentPage > 0) {
      setCurrentPage(currentPage - 1);
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

  const getRiskBadge = (score) => {
    if (score < 40) return 'bg-neon-green/20 text-neon-green border-neon-green/30';
    if (score < 70) return 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30';
    return 'bg-neon-red/20 text-neon-red border-neon-red/30';
  };

  const getSignalBadge = (signal) => {
    const badges = {
      STRONG: 'bg-neon-green/20 text-neon-green border-neon-green/30',
      MEDIUM: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
      WEAK: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
      NONE: 'bg-gray-700/20 text-gray-500 border-gray-700/30'
    };
    return badges[signal] || badges.NONE;
  };

  const handleTokenClick = (token) => {
    if (onSelectToken) {
      onSelectToken(token);
    }
  };

  const handleTradeClick = (e, token) => {
    e.stopPropagation();
    setSelectedToken(token);
    setShowTradeModal(true);
  };

  return (
    <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="token-scanner">
      <CardHeader className="border-b border-[#1E293B]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-neon-cyan animate-pulse" />
            <CardTitle className="font-heading">{t('scanner.tokenScanner')}</CardTitle>
            <Badge variant="outline" className="border-neon-cyan/30 text-neon-cyan">
              {filteredTokens.length} / {tokens.length} {t('scanner.tokens')}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('scanner.searchTokens')}
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCurrentPage(0); // Reset to first page on search
                }}
                className="pl-9 w-64 bg-[#0F172A] border-[#1E293B]"
                data-testid="token-search"
              />
            </div>
            <Button 
              variant={filterPassed ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                setFilterPassed(!filterPassed);
                setCurrentPage(0);
              }}
              className={filterPassed ? 'bg-neon-green text-black' : ''}
            >
              <Filter className="w-4 h-4 mr-1" />
              {t('scanner.safeOnly')}
            </Button>
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
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#1E293B]">
            <div className="text-sm text-muted-foreground">
              Zeige {currentPage * PAGE_SIZE + 1} - {Math.min((currentPage + 1) * PAGE_SIZE, filteredTokens.length)} von {filteredTokens.length} Tokens
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={goToPrevPage}
                disabled={currentPage === 0}
              >
                <ChevronLeft className="w-4 h-4" />
                Zurück
              </Button>
              <span className="text-sm px-3 py-1 bg-[#1E293B] rounded">
                Seite {currentPage + 1} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={goToNextPage}
                disabled={currentPage >= totalPages - 1}
              >
                Weiter
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[600px]">
          <div className="divide-y divide-[#1E293B]">
            {/* Header Row */}
            <div className="grid grid-cols-12 gap-2 px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground bg-[#050505] sticky top-0 z-10">
              <div className="col-span-3">{t('scanner.token')}</div>
              <div className="col-span-1 text-right">{t('scanner.price')}</div>
              <div className="col-span-1 text-right">{t('scanner.change5m')}</div>
              <div className="col-span-1 text-right">{t('scanner.change1h')}</div>
              <div className="col-span-1 text-right">{t('scanner.liq')}</div>
              <div className="col-span-1 text-right">{t('scanner.buySellRatio')}</div>
              <div className="col-span-2 text-center">{t('scanner.signal')}</div>
              <div className="col-span-2 text-center">Risk</div>
            </div>

            {/* Token Rows */}
            {loading && tokens.length === 0 ? (
              <div className="flex items-center justify-center h-40">
                <RefreshCw className="w-6 h-6 animate-spin text-neon-cyan" />
              </div>
            ) : paginatedTokens.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
                <Search className="w-8 h-8 mb-2" />
                <p>No tokens found</p>
              </div>
            ) : (
              paginatedTokens.map((token, index) => (
                <div
                  key={token.address}
                  className={`grid grid-cols-12 gap-2 px-4 py-3 hover:bg-white/5 cursor-pointer transition-colors group ${
                    token.signal_strength === 'STRONG' ? 'bg-neon-green/5' : ''
                  }`}
                  onClick={() => handleTokenClick(token)}
                  data-testid={`token-row-${index}`}
                >
                  {/* Token Info */}
                  <div className="col-span-3 flex items-center gap-3">
                    <div className="relative">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-xs font-bold">
                        {token.symbol.slice(0, 2)}
                      </div>
                      {token.signal_strength === 'STRONG' && (
                        <div className="absolute -top-1 -right-1 w-3 h-3 bg-neon-green rounded-full animate-pulse" />
                      )}
                    </div>
                    <div className="overflow-hidden">
                      <div className="font-semibold truncate group-hover:text-neon-cyan transition-colors flex items-center gap-1">
                        {token.symbol}
                        {token.risk_analysis?.passed_filters && (
                          <Check className="w-3 h-3 text-neon-green" />
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground truncate max-w-[150px]">
                        {token.name}
                      </div>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="col-span-1 text-right font-mono text-sm self-center">
                    ${formatPrice(token.price_usd)}
                  </div>

                  {/* 5m Change */}
                  <div className={`col-span-1 text-right font-mono text-sm flex items-center justify-end gap-1 self-center ${
                    token.price_change_5m >= 0 ? 'text-neon-green' : 'text-neon-red'
                  }`}>
                    {token.price_change_5m >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {Math.abs(token.price_change_5m || 0).toFixed(1)}%
                  </div>

                  {/* 1h Change */}
                  <div className={`col-span-1 text-right font-mono text-sm self-center ${
                    token.price_change_1h >= 0 ? 'text-neon-green' : 'text-neon-red'
                  }`}>
                    {Math.abs(token.price_change_1h || 0).toFixed(1)}%
                  </div>

                  {/* Liquidity */}
                  <div className="col-span-1 text-right font-mono text-sm text-muted-foreground self-center">
                    {formatNumber(token.liquidity)}
                  </div>

                  {/* Buy/Sell Ratio */}
                  <div className={`col-span-1 text-right font-mono text-sm self-center ${
                    token.buy_sell_ratio >= 1 ? 'text-neon-green' : 'text-neon-red'
                  }`}>
                    {token.buy_sell_ratio.toFixed(1)}x
                  </div>

                  {/* Signal */}
                  <div className="col-span-2 flex items-center justify-center">
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant="outline" 
                        className={`text-xs ${getSignalBadge(token.signal_strength)}`}
                      >
                        <Activity className="w-3 h-3 mr-1" />
                        {token.signal_strength}
                      </Badge>
                    </div>
                  </div>

                  {/* Risk Score */}
                  <div className="col-span-2 flex items-center justify-center gap-2">
                    <div className="w-12">
                      <Progress 
                        value={100 - (token.risk_analysis?.risk_score || 50)} 
                        className="h-1.5"
                      />
                    </div>
                    <Badge 
                      variant="outline" 
                      className={`text-xs min-w-[40px] justify-center ${getRiskBadge(token.risk_analysis?.risk_score || 50)}`}
                    >
                      {token.risk_analysis?.risk_score || 50}
                    </Badge>
                    {showTradeButton && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 px-2 text-neon-green hover:bg-neon-green/10"
                        onClick={(e) => handleTradeClick(e, token)}
                        data-testid={`trade-btn-${index}`}
                      >
                        Trade
                      </Button>
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
          onSuccess={fetchTokens}
        />
      )}
    </Card>
  );
};

export default TokenScanner;
