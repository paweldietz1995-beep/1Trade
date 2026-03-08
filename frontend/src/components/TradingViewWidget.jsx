import React, { useEffect, useRef, memo, useState } from 'react';
import { Eye, AlertCircle, TrendingUp } from 'lucide-react';

// Known tokens that have valid TradingView charts
const TRADINGVIEW_PAIRS = {
  'SOL': 'COINBASE:SOLUSD',
  'SOLUSD': 'COINBASE:SOLUSD',
  'RAY': 'BINANCE:RAYUSDT',
  'JUP': 'BINANCE:JUPUSDT',
  'BONK': 'BINANCE:BONKUSDT',
  'WIF': 'BINANCE:WIFUSDT',
  'ORCA': 'BINANCE:ORCAUSDT',
  'PYTH': 'BINANCE:PYTHUSDT',
  'JTO': 'BINANCE:JTOUSDT',
  'RENDER': 'BINANCE:RENDERUSDT',
  'HNT': 'BINANCE:HNTUSDT',
};

const TradingViewWidget = memo(({ symbol, selectedToken = null, interval = '15' }) => {
  const containerRef = useRef(null);
  const scriptAddedRef = useRef(false);
  const [chartSymbol, setChartSymbol] = useState(null);
  const [showPlaceholder, setShowPlaceholder] = useState(true);

  // Determine valid chart symbol
  useEffect(() => {
    // No token selected - show placeholder
    if (!selectedToken && !symbol) {
      setShowPlaceholder(true);
      setChartSymbol(null);
      return;
    }

    const tokenSymbol = selectedToken?.symbol || symbol;
    
    // Check if we have a known TradingView pair for this token
    const upperSymbol = tokenSymbol?.toUpperCase();
    
    if (upperSymbol && TRADINGVIEW_PAIRS[upperSymbol]) {
      setChartSymbol(TRADINGVIEW_PAIRS[upperSymbol]);
      setShowPlaceholder(false);
    } else if (tokenSymbol && tokenSymbol.includes(':')) {
      // Already has exchange prefix
      setChartSymbol(tokenSymbol);
      setShowPlaceholder(false);
    } else {
      // Unknown token - show placeholder with token info
      setChartSymbol(null);
      setShowPlaceholder(true);
    }
  }, [symbol, selectedToken]);

  // Load TradingView widget when we have a valid symbol
  useEffect(() => {
    if (showPlaceholder || !chartSymbol) {
      scriptAddedRef.current = false;
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    // Clear container
    container.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: chartSymbol,
      interval: interval,
      timezone: 'Etc/UTC',
      theme: 'dark',
      style: '1',
      locale: 'en',
      enable_publishing: false,
      backgroundColor: 'rgba(5, 5, 5, 1)',
      gridColor: 'rgba(30, 41, 59, 0.5)',
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      hide_volume: false,
      support_host: 'https://www.tradingview.com'
    });

    container.appendChild(script);
    scriptAddedRef.current = true;

    return () => {
      scriptAddedRef.current = false;
    };
  }, [chartSymbol, interval, showPlaceholder]);

  // Placeholder when no valid chart
  if (showPlaceholder) {
    return (
      <div 
        className="h-full w-full flex flex-col items-center justify-center bg-[#050505] border border-[#1E293B] rounded-sm"
        data-testid="tradingview-placeholder"
      >
        {selectedToken ? (
          // Token selected but no TradingView chart available
          <>
            <div className="w-20 h-20 rounded-full bg-neon-violet/20 flex items-center justify-center mb-4">
              <TrendingUp className="w-10 h-10 text-neon-violet" />
            </div>
            <p className="text-lg font-semibold text-foreground mb-1">
              {selectedToken.symbol}
            </p>
            <p className="text-sm text-muted-foreground mb-4">
              ${selectedToken.price_usd?.toFixed(8) || '0.00'}
            </p>
            <div className="bg-[#0A0A0A] border border-[#1E293B] rounded-sm p-4 max-w-sm">
              <div className="flex items-center gap-2 text-yellow-500 mb-2">
                <AlertCircle className="w-4 h-4" />
                <span className="text-sm font-medium">Chart Unavailable</span>
              </div>
              <p className="text-xs text-muted-foreground">
                TradingView charts are not available for this memecoin. 
                Use DEX Screener or Birdeye for price charts.
              </p>
            </div>
            {selectedToken.pair_address && (
              <a 
                href={`https://dexscreener.com/solana/${selectedToken.pair_address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 text-sm text-neon-cyan hover:underline"
              >
                View on DEX Screener →
              </a>
            )}
          </>
        ) : (
          // No token selected
          <>
            <Eye className="w-16 h-16 text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground text-lg mb-2">Select a token to display chart</p>
            <p className="text-xs text-muted-foreground/50">
              Click on any token in the Scanner to view its chart
            </p>
            <div className="mt-6 grid grid-cols-3 gap-2 text-xs">
              <span className="px-2 py-1 bg-[#0A0A0A] border border-[#1E293B] rounded text-muted-foreground">SOL/USD</span>
              <span className="px-2 py-1 bg-[#0A0A0A] border border-[#1E293B] rounded text-muted-foreground">JUP/USD</span>
              <span className="px-2 py-1 bg-[#0A0A0A] border border-[#1E293B] rounded text-muted-foreground">RAY/USD</span>
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div 
      ref={containerRef} 
      className="tradingview-widget-container h-full w-full"
      data-testid="tradingview-chart"
    />
  );
});

TradingViewWidget.displayName = 'TradingViewWidget';

export default TradingViewWidget;
