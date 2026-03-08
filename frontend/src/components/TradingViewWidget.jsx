import React, { useEffect, useRef, memo, useState } from 'react';
import { TrendingUp, ExternalLink } from 'lucide-react';

// Known tokens that have valid TradingView charts (major pairs only)
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
  'MOBILE': 'BINANCE:MOBILEUSDT',
  'W': 'BINANCE:WUSDT',
};

const TradingViewWidget = memo(({ symbol, selectedToken = null, interval = '15' }) => {
  const containerRef = useRef(null);
  const scriptAddedRef = useRef(false);
  const [chartType, setChartType] = useState('none'); // 'tradingview', 'dexscreener', 'none'
  const [chartSymbol, setChartSymbol] = useState(null);
  const [dexScreenerUrl, setDexScreenerUrl] = useState(null);

  // Determine which chart to show
  useEffect(() => {
    // No token selected - show placeholder
    if (!selectedToken && !symbol) {
      setChartType('none');
      setChartSymbol(null);
      setDexScreenerUrl(null);
      return;
    }

    const tokenSymbol = selectedToken?.symbol || symbol;
    const upperSymbol = tokenSymbol?.toUpperCase();
    
    // Check if it's a major pair with TradingView support
    if (upperSymbol && TRADINGVIEW_PAIRS[upperSymbol]) {
      setChartType('tradingview');
      setChartSymbol(TRADINGVIEW_PAIRS[upperSymbol]);
      setDexScreenerUrl(null);
    } else if (tokenSymbol && tokenSymbol.includes(':')) {
      // Already has exchange prefix - use TradingView
      setChartType('tradingview');
      setChartSymbol(tokenSymbol);
      setDexScreenerUrl(null);
    } else if (selectedToken?.pair_address || selectedToken?.address) {
      // Pump.fun / memecoin - use DexScreener embed
      const address = selectedToken.pair_address || selectedToken.address;
      setChartType('dexscreener');
      setChartSymbol(null);
      setDexScreenerUrl(`https://dexscreener.com/solana/${address}?embed=1&theme=dark&trades=0&info=0`);
    } else {
      setChartType('none');
      setChartSymbol(null);
      setDexScreenerUrl(null);
    }
  }, [symbol, selectedToken]);

  // Load TradingView widget
  useEffect(() => {
    if (chartType !== 'tradingview' || !chartSymbol) {
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
  }, [chartType, chartSymbol, interval]);

  // Render DexScreener embed
  if (chartType === 'dexscreener' && dexScreenerUrl) {
    return (
      <div className="h-full w-full relative" data-testid="dexscreener-chart">
        {/* Header with token info */}
        <div className="absolute top-2 left-2 z-10 flex items-center gap-2 bg-[#0A0A0A]/90 px-3 py-1.5 rounded border border-[#1E293B]">
          <TrendingUp className="w-4 h-4 text-neon-violet" />
          <span className="text-sm font-semibold text-foreground">{selectedToken?.symbol}</span>
          <span className="text-xs text-muted-foreground">${selectedToken?.price_usd?.toFixed(8) || '0.00'}</span>
          <a 
            href={`https://dexscreener.com/solana/${selectedToken?.pair_address || selectedToken?.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 text-neon-cyan hover:text-neon-cyan/80"
          >
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        
        {/* DexScreener iframe */}
        <iframe
          src={dexScreenerUrl}
          title={`${selectedToken?.symbol} Chart`}
          className="w-full h-full border-0 rounded"
          style={{ 
            backgroundColor: '#050505',
            minHeight: '500px'
          }}
          allow="clipboard-write"
          loading="lazy"
        />
      </div>
    );
  }

  // Render TradingView chart
  if (chartType === 'tradingview' && chartSymbol) {
    return (
      <div 
        ref={containerRef} 
        className="tradingview-widget-container h-full w-full"
        data-testid="tradingview-chart"
      />
    );
  }

  // Placeholder when no token selected
  return (
    <div 
      className="h-full w-full flex flex-col items-center justify-center bg-[#050505] border border-[#1E293B] rounded-sm"
      data-testid="chart-placeholder"
    >
      <TrendingUp className="w-16 h-16 text-muted-foreground/30 mb-4" />
      <p className="text-muted-foreground text-lg mb-2">Select a token to display chart</p>
      <p className="text-xs text-muted-foreground/50 mb-4">
        Click on any token in the Scanner tab
      </p>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <span className="px-3 py-1.5 bg-[#0A0A0A] border border-[#1E293B] rounded text-muted-foreground">SOL/USD</span>
        <span className="px-3 py-1.5 bg-[#0A0A0A] border border-[#1E293B] rounded text-muted-foreground">JUP/USD</span>
        <span className="px-3 py-1.5 bg-[#0A0A0A] border border-[#1E293B] rounded text-muted-foreground">Pump Tokens</span>
      </div>
      <p className="mt-4 text-xs text-neon-cyan/70">
        Major pairs → TradingView | Pump tokens → DexScreener
      </p>
    </div>
  );
});

TradingViewWidget.displayName = 'TradingViewWidget';

export default TradingViewWidget;
