import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { useWallet } from '@solana/wallet-adapter-react';
import {
  Activity,
  Wifi,
  WifiOff,
  Database,
  Bot,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  AlertTriangle,
  Shield,
  Radio,
  Wallet
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { toast } from 'sonner';

const DebugPanel = ({ isOpen, onClose }) => {
  const { API_URL } = useApp();
  const { connected, publicKey, wallet } = useWallet();
  
  const [systemHealth, setSystemHealth] = useState(null);
  const [liveCheckResult, setLiveCheckResult] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  const addLog = (type, message) => {
    const log = {
      time: new Date().toLocaleTimeString(),
      type,
      message
    };
    setLogs(prev => [...prev.slice(-49), log]);
  };

  const fetchSystemHealth = useCallback(async () => {
    try {
      addLog('system', 'Checking system health...');
      const response = await axios.get(`${API_URL}/system/health`);
      setSystemHealth(response.data);
      
      if (response.data.overall_ok) {
        addLog('success', 'All systems operational');
      } else {
        addLog('error', 'Some systems have issues');
      }
    } catch (error) {
      addLog('error', `Health check failed: ${error.message}`);
      setSystemHealth(null);
    }
  }, [API_URL]);

  const fetchLiveCheckResult = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/trading/can-enable-live`);
      setLiveCheckResult(response.data);
      
      if (response.data.can_enable) {
        addLog('success', 'Live trading can be enabled');
      } else {
        response.data.blockers.forEach(b => addLog('error', `Blocker: ${b}`));
      }
    } catch (error) {
      addLog('error', `Live check failed: ${error.message}`);
    }
  }, [API_URL]);

  const fetchWalletBalance = useCallback(async () => {
    if (!connected || !publicKey) {
      addLog('warning', 'Wallet not connected');
      return;
    }
    
    try {
      addLog('wallet', 'Fetching wallet balance via backend...');
      const response = await axios.get(`${API_URL}/wallet/balance`, {
        params: { address: publicKey.toBase58() }
      });
      
      if (response.data.success) {
        addLog('success', `Balance: ${response.data.balance} SOL (via ${response.data.endpoint})`);
      } else {
        addLog('error', `Balance fetch failed: ${response.data.error}`);
      }
    } catch (error) {
      addLog('error', `Wallet balance error: ${error.message}`);
    }
  }, [API_URL, connected, publicKey]);

  const resetLossStreak = async () => {
    try {
      addLog('system', 'Resetting loss streak...');
      const response = await axios.post(`${API_URL}/trading/reset-loss-streak`);
      
      if (response.data.success) {
        addLog('success', `Loss streak reset. Previous: ${response.data.previous_streak}`);
        toast.success('Loss streak reset', {
          description: response.data.message
        });
        // Refresh data
        fetchSystemHealth();
        fetchLiveCheckResult();
      }
    } catch (error) {
      addLog('error', `Reset failed: ${error.message}`);
      toast.error('Failed to reset loss streak');
    }
  };

  const refreshAll = useCallback(async () => {
    setLoading(true);
    addLog('system', 'Refreshing all diagnostics...');
    
    await Promise.all([
      fetchSystemHealth(),
      fetchLiveCheckResult(),
      connected && publicKey ? fetchWalletBalance() : Promise.resolve()
    ]);
    
    setLoading(false);
  }, [fetchSystemHealth, fetchLiveCheckResult, fetchWalletBalance, connected, publicKey]);

  useEffect(() => {
    if (isOpen) {
      refreshAll();
      const interval = setInterval(refreshAll, 10000);
      return () => clearInterval(interval);
    }
  }, [isOpen, refreshAll]);

  if (!isOpen) return null;

  const StatusIndicator = ({ ok, label, details }) => (
    <div className="flex items-center justify-between p-2 bg-[#050505] rounded-sm border border-[#1E293B]">
      <div className="flex items-center gap-2">
        {ok ? (
          <CheckCircle className="w-4 h-4 text-neon-green" />
        ) : (
          <XCircle className="w-4 h-4 text-neon-red" />
        )}
        <span className={ok ? 'text-neon-green' : 'text-neon-red'}>{label}</span>
      </div>
      {details && (
        <span className="text-xs text-muted-foreground">{details}</span>
      )}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <Card className="bg-[#0A0A0A] border-[#1E293B] w-full max-w-3xl max-h-[85vh] overflow-hidden">
        <CardHeader className="border-b border-[#1E293B]">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-neon-cyan" />
              System Diagnostics
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={refreshAll}
                disabled={loading}
              >
                <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button variant="ghost" size="sm" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="p-4 space-y-4 overflow-y-auto max-h-[calc(85vh-80px)]">
          {/* Overall Status */}
          {systemHealth && (
            <div className={`p-4 rounded-sm border ${
              systemHealth.overall_ok 
                ? 'bg-neon-green/5 border-neon-green/20' 
                : 'bg-neon-red/5 border-neon-red/20'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {systemHealth.overall_ok ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-neon-green" />
                    <span className="font-semibold text-neon-green">All Systems Operational</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-5 h-5 text-neon-red" />
                    <span className="font-semibold text-neon-red">System Issues Detected</span>
                  </>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                Last check: {new Date(systemHealth.timestamp).toLocaleTimeString()}
              </div>
            </div>
          )}

          {/* Status Grid */}
          <div className="grid grid-cols-2 gap-3">
            {/* Wallet */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                <Wallet className="w-4 h-4 text-neon-cyan" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Wallet</span>
              </div>
              <StatusIndicator 
                ok={connected} 
                label={connected ? 'Connected' : 'Disconnected'}
                details={connected ? wallet?.adapter?.name : null}
              />
              {connected && publicKey && (
                <div className="mt-2 text-xs text-muted-foreground font-mono">
                  {publicKey.toBase58().substring(0, 12)}...
                </div>
              )}
            </div>

            {/* RPC */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                {systemHealth?.rpc_ok ? (
                  <Wifi className="w-4 h-4 text-neon-green" />
                ) : (
                  <WifiOff className="w-4 h-4 text-neon-red" />
                )}
                <span className="text-xs uppercase tracking-wider text-muted-foreground">RPC</span>
              </div>
              <StatusIndicator 
                ok={systemHealth?.rpc_ok} 
                label={systemHealth?.rpc_ok ? 'Connected' : 'Failed'}
                details={systemHealth?.details?.rpc?.latency_ms ? `${systemHealth.details.rpc.latency_ms}ms` : null}
              />
            </div>

            {/* Scanner */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                <Radio className="w-4 h-4 text-neon-violet" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Scanner</span>
              </div>
              <StatusIndicator 
                ok={systemHealth?.scanner_ok} 
                label={systemHealth?.scanner_ok ? 'Active' : 'Failed'}
                details={systemHealth?.details?.scanner?.pairs_found ? `${systemHealth.details.scanner.pairs_found} pairs` : null}
              />
            </div>

            {/* Database */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                <Database className="w-4 h-4 text-neon-green" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Database</span>
              </div>
              <StatusIndicator 
                ok={systemHealth?.database_ok} 
                label={systemHealth?.database_ok ? 'Connected' : 'Failed'}
              />
            </div>
          </div>

          {/* Auto Trading Status */}
          <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
            <div className="flex items-center gap-2 mb-2">
              <Bot className="w-4 h-4 text-neon-green" />
              <span className="text-xs uppercase tracking-wider text-muted-foreground">Auto Trading Engine</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Status:</span>
                <span className={`ml-2 ${systemHealth?.details?.trading_engine?.auto_trading_active ? 'text-neon-green' : 'text-muted-foreground'}`}>
                  {systemHealth?.details?.trading_engine?.auto_trading_active ? 'ACTIVE' : 'Stopped'}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Scans:</span>
                <span className="ml-2 font-mono text-neon-cyan">
                  {systemHealth?.details?.trading_engine?.scan_count || 0}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Trades:</span>
                <span className="ml-2 font-mono text-neon-green">
                  {systemHealth?.details?.trading_engine?.trades_executed || 0}
                </span>
              </div>
            </div>
          </div>

          {/* Live Trading Safety Check */}
          {liveCheckResult && (
            <div className={`p-3 rounded-sm border ${
              liveCheckResult.can_enable 
                ? 'bg-neon-green/5 border-neon-green/20' 
                : 'bg-neon-red/5 border-neon-red/20'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Live Trading Safety</span>
              </div>
              
              {liveCheckResult.can_enable ? (
                <div className="flex items-center gap-2 text-neon-green">
                  <CheckCircle className="w-4 h-4" />
                  <span>Live trading can be enabled safely</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-neon-red font-semibold">Blockers:</div>
                  {liveCheckResult.blockers.map((blocker, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm text-neon-red">
                      <XCircle className="w-3 h-3 flex-shrink-0" />
                      <span>{blocker}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {liveCheckResult.warnings?.length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="text-yellow-500 text-xs font-semibold">Warnings:</div>
                  {liveCheckResult.warnings.map((warning, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-xs text-yellow-500">
                      <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                      <span>{warning}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Loss Streak Reset Button */}
              {liveCheckResult.portfolio?.loss_streak > 0 && (
                <div className="mt-3 pt-3 border-t border-[#1E293B]">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={resetLossStreak}
                    className="border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Reset Loss Streak ({liveCheckResult.portfolio.loss_streak})
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Activity Log */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-muted-foreground" />
              <span className="text-xs uppercase tracking-wider text-muted-foreground">Activity Log</span>
            </div>
            <ScrollArea className="h-32 p-2 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="space-y-1 font-mono text-xs">
                {logs.length === 0 ? (
                  <div className="text-muted-foreground">No activity yet...</div>
                ) : (
                  logs.slice().reverse().map((log, idx) => (
                    <div key={idx} className="flex gap-2">
                      <span className="text-muted-foreground">[{log.time}]</span>
                      <span className={
                        log.type === 'error' ? 'text-neon-red' :
                        log.type === 'success' ? 'text-neon-green' :
                        log.type === 'warning' ? 'text-yellow-500' :
                        log.type === 'wallet' ? 'text-neon-cyan' :
                        'text-foreground'
                      }>
                        {log.message}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Quick Actions */}
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              size="sm"
              onClick={fetchWalletBalance}
              disabled={!connected}
              className="border-neon-cyan/30 text-neon-cyan"
            >
              <Wallet className="w-4 h-4 mr-2" />
              Test Balance Fetch
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default DebugPanel;
