import React, { useEffect, useRef, memo } from 'react';

const TradingViewWidget = memo(({ symbol = 'SOLUSD', interval = '15' }) => {
  const containerRef = useRef(null);
  const scriptAddedRef = useRef(false);

  useEffect(() => {
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
      symbol: symbol,
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
  }, [symbol, interval]);

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
