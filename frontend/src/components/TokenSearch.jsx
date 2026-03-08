import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { 
  Search, 
  X, 
  TrendingUp, 
  TrendingDown,
  ExternalLink,
  Loader2
} from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

const TokenSearch = ({ onSelectToken, isOpen, onClose }) => {
  const { API_URL } = useApp();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [recentTokens, setRecentTokens] = useState([]);

  // Load recent tokens from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('recent_tokens');
    if (stored) {
      try {
        setRecentTokens(JSON.parse(stored));
      } catch {
        // Invalid JSON
      }
    }
  }, []);

  const searchTokens = useCallback(async (searchQuery) => {
    if (searchQuery.length < 2) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      // Check if it's a contract address (base58 string, 32-44 chars)
      const isAddress = /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(searchQuery);
      
      if (isAddress) {
        // Search by address
        const response = await axios.get(`${API_URL}/tokens/${searchQuery}`);
        setResults([response.data]);
      } else {
        // Search by name/symbol from DEX Screener
        const response = await axios.get(
          `https://api.dexscreener.com/latest/dex/search`,
          { params: { q: searchQuery } }
        );
        
        const pairs = response.data.pairs || [];
        const solanaTokens = pairs
          .filter(p => p.chainId === 'solana')
          .slice(0, 10)
          .map(p => ({
            address: p.baseToken.address,
            name: p.baseToken.name,
            symbol: p.baseToken.symbol,
            price_usd: parseFloat(p.priceUsd || 0),
            price_change_24h: parseFloat(p.priceChange?.h24 || 0),
            liquidity: parseFloat(p.liquidity?.usd || 0),
            volume_24h: parseFloat(p.volume?.h24 || 0),
            market_cap: parseFloat(p.fdv || 0),
            pairAddress: p.pairAddress
          }));
        
        setResults(solanaTokens);
      }
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    }
    setLoading(false);
  }, [API_URL]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      searchTokens(query);
    }, 300);
    return () => clearTimeout(debounce);
  }, [query, searchTokens]);

  const handleSelect = (token) => {
    // Add to recent tokens
    const updated = [token, ...recentTokens.filter(t => t.address !== token.address)].slice(0, 5);
    setRecentTokens(updated);
    localStorage.setItem('recent_tokens', JSON.stringify(updated));
    
    onSelectToken(token);
    onClose();
    setQuery('');
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

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-[#0A0A0A] border-[#1E293B] max-w-lg" data-testid="token-search-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading flex items-center gap-2">
            <Search className="w-5 h-5 text-neon-cyan" />
            Search Token
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4">
          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search by name, symbol, or contract address..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9 bg-[#0F172A] border-[#1E293B]"
              autoFocus
              data-testid="token-search-input"
            />
            {query && (
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                onClick={() => setQuery('')}
              >
                <X className="w-4 h-4" />
              </Button>
            )}
          </div>

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-neon-cyan" />
            </div>
          )}

          {/* Results */}
          {!loading && results.length > 0 && (
            <ScrollArea className="h-80">
              <div className="space-y-2">
                {results.map((token, idx) => (
                  <div
                    key={token.address + idx}
                    className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B] hover:border-neon-cyan/50 cursor-pointer transition-colors"
                    onClick={() => handleSelect(token)}
                    data-testid={`search-result-${idx}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-sm font-bold">
                        {token.symbol?.slice(0, 2) || '??'}
                      </div>
                      <div>
                        <div className="font-semibold">{token.symbol}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-[150px]">
                          {token.name}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm">${formatPrice(token.price_usd)}</div>
                      <div className={`text-xs flex items-center justify-end gap-1 ${token.price_change_24h >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                        {token.price_change_24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {Math.abs(token.price_change_24h).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}

          {/* No Results */}
          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Search className="w-8 h-8 mx-auto mb-2" />
              <p>No tokens found</p>
            </div>
          )}

          {/* Recent Tokens */}
          {!loading && !query && recentTokens.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
                Recent Searches
              </div>
              <div className="space-y-2">
                {recentTokens.map((token, idx) => (
                  <div
                    key={token.address}
                    className="flex items-center justify-between p-2 bg-[#050505] rounded-sm border border-[#1E293B] hover:border-neon-cyan/50 cursor-pointer transition-colors"
                    onClick={() => handleSelect(token)}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-gradient-to-br from-neon-violet to-neon-cyan flex items-center justify-center text-xs font-bold">
                        {token.symbol?.slice(0, 2)}
                      </div>
                      <span className="font-semibold text-sm">{token.symbol}</span>
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">
                      ${formatPrice(token.price_usd)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Instructions */}
          {!loading && !query && recentTokens.length === 0 && (
            <div className="text-center py-8 text-muted-foreground text-sm">
              <p>Enter a token name, symbol, or contract address</p>
              <p className="mt-1 text-xs">Example: BONK, WIF, or paste a Solana address</p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default TokenSearch;
