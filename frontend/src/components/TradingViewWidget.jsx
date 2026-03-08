import React, { useEffect, useRef, memo, useState } from 'react';
import { Eye, AlertCircle } from 'lucide-react';

// Valid symbol patterns for TradingView
const VALID_EXCHANGES = ['COINBASE', 'BINANCE', 'RAYDIUM', 'ORCA', 'JUPITER'];

const TradingViewWidget = memo(({ symbol = 'COINBASE:SOLUSD', interval = '15' }) => {
  const containerRef = useRef(null);
  const scriptAddedRef = useRef(false);
  const [isValidSymbol, setIsValidSymbol] = useState(true);
  const [currentSymbol, setCurrentSymbol] = useState(symbol);

  // Validate and normalize symbol
  const normalizeSymbol = (sym) => {
    if (!sym) return null;
    
    // Check if symbol has exchange prefix
    const hasExchange = VALID_EXCHANGES.some(ex => sym.toUpperCase().startsWith(ex + ':'));
    
    // If it's a random memecoin address or invalid format, return null
    if (sym.length > 50) return null; // Token address, not a symbol
    if (sym.includes('...')) return null; // Truncated address
    
    // Default to COINBASE:SOLUSD for safety
    if (!hasExchange && !sym.includes(':')) {
      // Check if it's a known token
      if (sym.toUpperCase() === 'SOL' || sym.toUpperCase() === 'SOLUSD') {
        return 'COINBASE:SOLUSD';
      }
      // For memecoins, we can't reliably get TradingView charts
      return null;
    }
    
    return sym;
  };

  useEffect(() => {
    const normalizedSymbol = normalizeSymbol(symbol);
    
    if (!normalizedSymbol) {
      setIsValidSymbol(false);
      setCurrentSymbol(null);
      return;
    }
    
    setIsValidSymbol(true);
    setCurrentSymbol(normalizedSymbol);
    
    // Reset script added flag when symbol changes
    if (scriptAddedRef.current && normalizedSymbol !== currentSymbol) {
      scriptAddedRef.current = false;
    }
    
    if (scriptAddedRef.current) return;
    
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
      symbol: normalizedSymbol,
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
  }, [symbol, interval, currentSymbol]);

  // Show placeholder for invalid symbols
  if (!isValidSymbol) {
    return (
      <div 
        className="h-full w-full flex flex-col items-center justify-center bg-[#050505] border border-[#1E293B] rounded-sm"
        data-testid="tradingview-placeholder"
      >
        <Eye className="w-16 h-16 text-muted-foreground/30 mb-4" />
        <p className="text-muted-foreground text-lg mb-2">Select a token to display chart</p>
        <p className="text-xs text-muted-foreground/50">
          Charts available for major pairs (SOL, RAY, JUP, etc.)
        </p>
        <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground/70">
          <AlertCircle className="w-4 h-4" />
          <span>Memecoin charts not available on TradingView</span>
        </div>
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
