import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { 
  Activity, TrendingUp, TrendingDown, AlertCircle, Clock, 
  Target, ShieldAlert, Search, Zap, XCircle 
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL + '/api';

const ActivityFeed = () => {
  const { t } = useTranslation();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchActivity = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/activity?limit=50`);
      setEvents(response.data);
    } catch (error) {
      console.error('Error fetching activity:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchActivity();
    const interval = setInterval(fetchActivity, 2000); // Update every 2 seconds
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
        return <TrendingDown className="w-4 h-4" />;
      case 'TP_HIT':
        return <Target className="w-4 h-4 text-green-400" />;
      case 'SL_HIT':
        return <XCircle className="w-4 h-4 text-red-400" />;
      case 'SIGNAL':
        return <Zap className="w-4 h-4 text-yellow-400" />;
      case 'SCAN':
        return <Search className="w-4 h-4 text-cyan-400" />;
      case 'ANTI_RUG':
        return <ShieldAlert className="w-4 h-4 text-orange-400" />;
      default:
        return <Activity className="w-4 h-4 text-gray-400" />;
    }
  };

  const getEventColor = (event) => {
    switch (event.type) {
      case 'BUY':
        return 'border-l-4 border-l-green-500 bg-green-500/5';
      case 'SELL':
        const pnl = event.data?.pnl_percent || 0;
        return pnl >= 0 
          ? 'border-l-4 border-l-green-500 bg-green-500/5' 
          : 'border-l-4 border-l-red-500 bg-red-500/5';
      case 'TP_HIT':
        return 'border-l-4 border-l-green-400 bg-green-400/10';
      case 'SL_HIT':
        return 'border-l-4 border-l-red-400 bg-red-400/10';
      case 'SIGNAL':
        return 'border-l-4 border-l-yellow-500 bg-yellow-500/5';
      case 'SCAN':
        return 'border-l-4 border-l-cyan-500 bg-cyan-500/5';
      case 'ANTI_RUG':
        return 'border-l-4 border-l-orange-500 bg-orange-500/5';
      default:
        return 'border-l-4 border-l-gray-500 bg-gray-500/5';
    }
  };

  const getEventLabel = (type) => {
    switch (type) {
      case 'BUY': return 'BOT KAUF';
      case 'SELL': return 'BOT VERKAUF';
      case 'TP_HIT': return 'TAKE PROFIT';
      case 'SL_HIT': return 'STOP LOSS';
      case 'SIGNAL': return 'SIGNAL';
      case 'SCAN': return 'SCAN';
      case 'ANTI_RUG': return 'RUG CHECK';
      default: return type;
    }
  };

  return (
    <div className="bg-[#0a0a0f] rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-cyan-400" />
          <h3 className="text-white font-medium">BOT AKTIVITÄT</h3>
          <span className="px-2 py-0.5 rounded-full text-xs bg-cyan-500/20 text-cyan-400">
            LIVE
          </span>
        </div>
        <span className="text-xs text-gray-500">{events.length} Events</span>
      </div>

      <div className="max-h-96 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-gray-500">
            <div className="animate-spin w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto" />
          </div>
        ) : events.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>Warte auf Bot-Aktivität...</p>
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
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-gray-400">
                          {getEventLabel(event.type)}
                        </span>
                        <span className="font-medium text-white truncate">
                          {event.token}
                        </span>
                      </div>
                      <span className="text-xs text-gray-500 flex items-center gap-1 whitespace-nowrap">
                        <Clock className="w-3 h-3" />
                        {formatTime(event.timestamp)}
                      </span>
                    </div>
                    
                    {/* BUY Event Details */}
                    {event.type === 'BUY' && (
                      <div className="mt-1 text-xs text-gray-400">
                        <span className="text-cyan-400">Entry: {formatPrice(event.data?.price)}</span>
                        <span className="mx-2">•</span>
                        <span>{event.data?.amount_sol?.toFixed(4)} SOL</span>
                        <span className="mx-2">•</span>
                        <span className="text-yellow-400">Score: {event.data?.signal_score}</span>
                      </div>
                    )}
                    
                    {/* SELL Event Details */}
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
                        <span className="text-gray-400">{event.data?.reason}</span>
                      </div>
                    )}
                    
                    {/* TP/SL Hit Details */}
                    {(event.type === 'TP_HIT' || event.type === 'SL_HIT') && (
                      <div className="mt-1 text-xs">
                        <span className={event.type === 'TP_HIT' ? 'text-green-400' : 'text-red-400'}>
                          {event.data?.message || `ROI: ${event.data?.roi?.toFixed(2)}%`}
                        </span>
                      </div>
                    )}
                    
                    {/* SIGNAL Details */}
                    {event.type === 'SIGNAL' && (
                      <div className="mt-1 text-xs text-gray-400">
                        <span className="text-yellow-400">{event.data?.strength}</span>
                        <span className="mx-2">•</span>
                        <span>Score: {event.data?.score}</span>
                      </div>
                    )}
                    
                    {/* SCAN Details */}
                    {event.type === 'SCAN' && (
                      <div className="mt-1 text-xs text-gray-400">
                        {event.data?.message}
                      </div>
                    )}
                    
                    {/* Anti-Rug Details */}
                    {event.type === 'ANTI_RUG' && (
                      <div className="mt-1 text-xs">
                        <span className={
                          event.data?.risk_level === 'HIGH' ? 'text-red-400' :
                          event.data?.risk_level === 'MEDIUM' ? 'text-orange-400' :
                          'text-green-400'
                        }>
                          Risk: {event.data?.risk_level}
                        </span>
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
