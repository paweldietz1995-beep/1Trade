import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { 
  Zap, 
  TrendingUp, 
  Shield, 
  AlertTriangle,
  RefreshCw,
  ArrowRight,
  Target,
  Percent
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import TradeModal from './TradeModal';

const TradingOpportunities = () => {
  const { API_URL } = useApp();
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [showTradeModal, setShowTradeModal] = useState(false);

  const fetchOpportunities = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_URL}/opportunities`);
      setOpportunities(response.data);
    } catch (error) {
      console.error('Error fetching opportunities:', error);
    }
    setLoading(false);
  }, [API_URL]);

  useEffect(() => {
    fetchOpportunities();
    const interval = setInterval(fetchOpportunities, 30000);
    return () => clearInterval(interval);
  }, [fetchOpportunities]);

  const getRiskColor = (level) => {
    const colors = {
      LOW: 'text-neon-green border-neon-green/30 bg-neon-green/10',
      MEDIUM: 'text-yellow-500 border-yellow-500/30 bg-yellow-500/10',
      HIGH: 'text-neon-red border-neon-red/30 bg-neon-red/10'
    };
    return colors[level] || colors.MEDIUM;
  };

  const handleTradeClick = (opportunity) => {
    setSelectedOpportunity(opportunity);
    setShowTradeModal(true);
  };

  return (
    <Card className="bg-[#0A0A0A] border-[#1E293B] h-full" data-testid="trading-opportunities">
      <CardHeader className="border-b border-[#1E293B]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-neon-green" />
            <CardTitle className="font-heading">Trading Opportunities</CardTitle>
            <Badge variant="outline" className="border-neon-green/30 text-neon-green animate-pulse">
              AI Powered
            </Badge>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={fetchOpportunities}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-4">
        {loading && opportunities.length === 0 ? (
          <div className="flex items-center justify-center h-40">
            <RefreshCw className="w-6 h-6 animate-spin text-neon-cyan" />
          </div>
        ) : opportunities.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
            <Zap className="w-8 h-8 mb-2" />
            <p>Scanning for opportunities...</p>
            <p className="text-sm">Check back in a moment</p>
          </div>
        ) : (
          <ScrollArea className="h-[320px]">
            <div className="space-y-3">
              {opportunities.map((opp, index) => (
                <div 
                  key={opp.id}
                  className="p-4 bg-[#050505] rounded-sm border border-[#1E293B] hover:border-neon-green/50 transition-colors cursor-pointer group"
                  onClick={() => handleTradeClick(opp)}
                  data-testid={`opportunity-${index}`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-neon-green to-neon-cyan flex items-center justify-center text-sm font-bold">
                        {opp.token.symbol.slice(0, 2)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold group-hover:text-neon-green transition-colors">
                            {opp.token.symbol}
                          </span>
                          <Badge className="bg-neon-green/20 text-neon-green border-none">
                            {opp.suggested_action}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground truncate max-w-[200px]">
                          {opp.token.name}
                        </div>
                      </div>
                    </div>
                    <Button 
                      size="sm" 
                      className="bg-neon-green text-black hover:bg-neon-green/90"
                      data-testid={`trade-btn-${index}`}
                    >
                      Trade
                      <ArrowRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div className="text-center p-2 bg-[#0A0A0A] rounded-sm">
                      <div className="flex items-center justify-center gap-1 text-xs text-muted-foreground mb-1">
                        <Target className="w-3 h-3" />
                        Confidence
                      </div>
                      <div className="font-mono font-semibold text-neon-cyan">
                        {opp.confidence.toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-center p-2 bg-[#0A0A0A] rounded-sm">
                      <div className="flex items-center justify-center gap-1 text-xs text-muted-foreground mb-1">
                        <TrendingUp className="w-3 h-3" />
                        Potential
                      </div>
                      <div className="font-mono font-semibold text-neon-green">
                        +{opp.potential_profit.toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-center p-2 bg-[#0A0A0A] rounded-sm">
                      <div className="flex items-center justify-center gap-1 text-xs text-muted-foreground mb-1">
                        <Shield className="w-3 h-3" />
                        Risk
                      </div>
                      <Badge variant="outline" className={`text-xs ${getRiskColor(opp.risk_level)}`}>
                        {opp.risk_level}
                      </Badge>
                    </div>
                  </div>

                  {/* Reason */}
                  <div className="text-xs text-muted-foreground bg-[#0A0A0A] p-2 rounded-sm">
                    <span className="text-neon-cyan">Signal:</span> {opp.reason}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>

      {/* Trade Modal */}
      {showTradeModal && selectedOpportunity && (
        <TradeModal
          token={selectedOpportunity.token}
          opportunity={selectedOpportunity}
          onClose={() => {
            setShowTradeModal(false);
            setSelectedOpportunity(null);
          }}
        />
      )}
    </Card>
  );
};

export default TradingOpportunities;
