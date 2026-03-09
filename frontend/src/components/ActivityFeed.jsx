import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Activity, TrendingUp, TrendingDown, AlertCircle, Clock } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL + '/api';

const ActivityFeed = () => {
  const { t } = useTranslation();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchActivity = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/activity?limit=30`);
      setEvents(response.data);
    } catch (error) {
      console.error('Error fetching activity:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchActivity();
    const interval = setInterval(fetchActivity, 3000);
    return () => clearInterval(interval);
  }, [fetchActivity]);

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatPrice = (price) => {
    if (!price) return '$0.00';
    if (price < 0.0001) return `$${price.toExponential(2)}`;
    if (price < 1) return `$${price.toFixed(6)}`;
    return `$${price.toFixed(2)}`;
  };

  const getEventIcon = (type) => {
    switch (type) {
      case 'BUY':
        return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'SELL':
        return <TrendingDown className="w-4 h-4 text-red-400" />;
      case 'SIGNAL':
        return <AlertCircle className="w-4 h-4 text-yellow-400" />;
      default:
        return <Activity className="w-4 h-4 text-gray-400" />;
    }
  };

  const getEventColor = (event) => {
    if (event.type === 'BUY') return 'border-green-500/30 bg-green-500/5';
    if (event.type === 'SELL') {
      const pnl = event.data?.pnl_percent || 0;
      return pnl >= 0 ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5';
    }
    return 'border-gray-500/30 bg-gray-500/5';
  };

  return (
    <div className="bg-[#0a0a0f] rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
        <Activity className="w-5 h-5 text-cyan-400" />
        <h3 className="text-white font-medium">{t('activity.title', 'Trading Activity')}</h3>
        <span className="px-2 py-0.5 rounded-full text-xs bg-cyan-500/20 text-cyan-400">
          {events.length}
        </span>
      </div>

      <div className="max-h-80 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-gray-500">
            <div className="animate-spin w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto" />
          </div>
        ) : events.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>{t('activity.noActivity', 'Keine Aktivität')}</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {events.map((event) => (
              <div
                key={event.id}
                className={`p-3 transition-colors hover:bg-gray-800/30 ${getEventColor(event)}`}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">{getEventIcon(event.type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-white truncate">
                        {event.type === 'BUY' ? 'KAUF' : event.type === 'SELL' ? 'VERKAUF' : event.type} {event.token}
                      </span>
                      <span className="text-xs text-gray-500 flex items-center gap-1 whitespace-nowrap">
                        <Clock className="w-3 h-3" />
                        {formatTime(event.timestamp)}
                      </span>
                    </div>
                    
                    {event.type === 'BUY' && (
                      <div className="mt-1 text-xs text-gray-400">
                        <span className="text-cyan-400">{formatPrice(event.data?.price)}</span>
                        <span className="mx-2">•</span>
                        <span>{event.data?.amount_sol?.toFixed(4)} SOL</span>
                        <span className="mx-2">•</span>
                        <span className="text-yellow-400">Score: {event.data?.signal_score?.toFixed(0)}</span>
                      </div>
                    )}
                    
                    {event.type === 'SELL' && (
                      <div className="mt-1 text-xs">
                        <span className={event.data?.pnl_percent >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {event.data?.pnl_percent >= 0 ? '+' : ''}{event.data?.pnl_percent?.toFixed(2)}%
                        </span>
                        <span className="mx-2 text-gray-500">•</span>
                        <span className={event.data?.pnl_sol >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {event.data?.pnl_sol >= 0 ? '+' : ''}{event.data?.pnl_sol?.toFixed(6)} SOL
                        </span>
                        <span className="mx-2 text-gray-500">•</span>
                        <span className="text-gray-400">{event.data?.reason || 'MANUAL'}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityFeed;
