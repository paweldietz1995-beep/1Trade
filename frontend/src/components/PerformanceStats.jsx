import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { 
  TrendingUp, 
  TrendingDown, 
  Target,
  Award,
  BarChart3,
  RefreshCw,
  Rocket,
  Shield,
  Zap
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Progress } from './ui/progress';

const PerformanceStats = ({ solPrice = 150 }) => {
  const { t } = useTranslation();
  const { API_URL } = useApp();
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/dashboard/snapshot`);
      setSnapshot(response.data);
      setError(null);
    } catch (err) {
      console.error('Dashboard snapshot error:', err);
      setError('Fehler beim Laden der Daten');
    } finally {
      setLoading(false);
    }
  }, [API_URL]);

  useEffect(() => {
    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, 5000);
    return () => clearInterval(interval);
  }, [fetchSnapshot]);

  if (loading) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]">
        <CardContent className="p-6 flex items-center justify-center">
          <RefreshCw className="w-6 h-6 animate-spin text-neon-cyan" />
        </CardContent>
      </Card>
    );
  }

  if (error || !snapshot) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]">
        <CardContent className="p-6 text-center text-muted-foreground">
          {error || 'Keine Daten verfügbar'}
        </CardContent>
      </Card>
    );
  }

  const { trades, pnl, performance, close_reasons, mega_stats, top_winners, scanner, bot_status } = snapshot;

  return (
    <div className="space-y-4">
      {/* Haupt-Metriken */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-[#0A0A0A] to-[#1a1a2e] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-2">
              <Target className="w-4 h-4" />
              <span>Win Rate</span>
            </div>
            <div className="text-2xl font-bold text-white">
              {performance?.win_rate?.toFixed(1) || 0}%
            </div>
            <Progress 
              value={performance?.win_rate || 0} 
              className="h-1 mt-2"
            />
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-[#0A0A0A] to-[#1a2e1a] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-2">
              <TrendingUp className="w-4 h-4 text-neon-green" />
              <span>Gesamt P&L</span>
            </div>
            <div className={`text-2xl font-bold ${pnl?.combined >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
              {pnl?.combined >= 0 ? '+' : ''}{pnl?.combined?.toFixed(4) || 0} SOL
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              ≈ ${((pnl?.combined || 0) * solPrice).toFixed(2)} USD
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-[#0A0A0A] to-[#2e1a2e] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-2">
              <Award className="w-4 h-4 text-yellow-400" />
              <span>Avg. Gewinn</span>
            </div>
            <div className="text-2xl font-bold text-neon-green">
              +{performance?.avg_win?.toFixed(1) || 0}%
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {performance?.winners || 0} Gewinner
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-[#0A0A0A] to-[#2e2a1a] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-2">
              <Rocket className="w-4 h-4 text-purple-400" />
              <span>MEGA Exits</span>
            </div>
            <div className="text-2xl font-bold text-purple-400">
              {mega_stats?.mega_exits || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              1000%+: {mega_stats?.ultra_1000_count || 0} | 2000%+: {mega_stats?.ultra_2000_count || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Close Reasons & Top Winners */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Ausstiegsgründe */}
        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Shield className="w-4 h-4 text-neon-cyan" />
              Ausstiegsgründe
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {close_reasons && Object.entries(close_reasons)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 8)
              .map(([reason, count]) => {
                const total = Object.values(close_reasons).reduce((a, b) => a + b, 0);
                const percent = (count / total * 100).toFixed(1);
                const isPositive = ['MEGA_500', 'ULTRA_1000', 'ULTRA_2000', 'TP_HIT', 'TRAILING_STOP'].includes(reason);
                
                return (
                  <div key={reason} className="flex items-center gap-2">
                    <div className="w-24 text-xs text-muted-foreground truncate">
                      {reason.replace(/_/g, ' ')}
                    </div>
                    <div className="flex-1">
                      <Progress 
                        value={parseFloat(percent)} 
                        className={`h-2 ${isPositive ? 'bg-neon-green/20' : 'bg-neon-red/20'}`}
                      />
                    </div>
                    <div className="w-16 text-xs text-right">
                      <span className={isPositive ? 'text-neon-green' : 'text-muted-foreground'}>
                        {count}
                      </span>
                      <span className="text-muted-foreground"> ({percent}%)</span>
                    </div>
                  </div>
                );
              })}
          </CardContent>
        </Card>

        {/* Top Gewinner */}
        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-neon-green" />
              Top Gewinner (Offen)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {top_winners && top_winners.slice(0, 8).map((trade, idx) => (
              <div key={idx} className="flex items-center justify-between py-1 border-b border-[#1E293B]/50 last:border-0">
                <div className="flex items-center gap-2">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    trade.pnl_percent >= 100 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-neon-green/20 text-neon-green'
                  }`}>
                    {idx + 1}
                  </div>
                  <span className="font-mono text-sm">{trade.symbol}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-neon-green font-bold">
                    +{trade.pnl_percent?.toFixed(1)}%
                  </span>
                  <span className="text-xs text-muted-foreground">
                    ({trade.remaining}% übrig)
                  </span>
                </div>
              </div>
            ))}
            {(!top_winners || top_winners.length === 0) && (
              <div className="text-center text-muted-foreground py-4">
                Keine offenen Gewinner-Positionen
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Scanner & Bot Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-muted-foreground text-sm">Offene Trades</span>
              <Zap className="w-4 h-4 text-neon-cyan" />
            </div>
            <div className="text-3xl font-bold text-white">
              {trades?.open_count || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              von max. {snapshot.config?.max_open_trades || 120}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-muted-foreground text-sm">Geschlossene Trades</span>
              <BarChart3 className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-3xl font-bold text-white">
              {trades?.closed_count || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Heute: {bot_status?.trades_today || 0} | Scans: {bot_status?.scan_count || 0}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#0A0A0A] border-[#1E293B]">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-muted-foreground text-sm">Scanner</span>
              <RefreshCw className={`w-4 h-4 ${bot_status?.is_running ? 'text-neon-green animate-spin' : 'text-muted-foreground'}`} />
            </div>
            <div className="text-3xl font-bold text-white">
              {scanner?.tokens_total || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {scanner?.healthy || 0}/{scanner?.total_sources || 0} Quellen aktiv
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default PerformanceStats;
