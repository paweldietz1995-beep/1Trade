import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import {
  Activity,
  Wifi,
  WifiOff,
  Database,
  Bot,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  TrendingUp
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';

const DebugPanel = ({ isOpen, onClose }) => {
  const { API_URL } = useApp();
  const { connected, publicKey, wallet } = useWallet();
  const { connection } = useConnection();
  
  const [status, setStatus] = useState({
    wallet: { connected: false, address: null, balance: null },
    rpc: { healthy: false, endpoint: null, latency: null },
    backend: { healthy: false, version: null },
    scanner: { active: false, lastScan: null, tokenCount: 0 },
    autoTrading: { running: false, scanCount: 0, tradesExecuted: 0 }
  });
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

  const checkRpcHealth = useCallback(async () => {
    if (!connection) {
      setStatus(prev => ({
        ...prev,
        rpc: { healthy: false, endpoint: null, latency: null }
      }));
      return;
    }

    try {
      const start = Date.now();
      await connection.getSlot();
      const latency = Date.now() - start;
      
      setStatus(prev => ({
        ...prev,
        rpc: { 
          healthy: true, 
          endpoint: connection.rpcEndpoint?.substring(0, 30) + '...', 
          latency 
        }
      }));
      addLog('rpc', `RPC healthy (${latency}ms)`);
    } catch (error) {
      setStatus(prev => ({
        ...prev,
        rpc: { healthy: false, endpoint: null, latency: null }
      }));
      addLog('error', `RPC error: ${error.message}`);
    }
  }, [connection]);

  const checkBackendHealth = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/health`);
      setStatus(prev => ({
        ...prev,
        backend: { healthy: true, version: '2.0.0' }
      }));
      addLog('backend', 'Backend healthy');
    } catch (error) {
      setStatus(prev => ({
        ...prev,
        backend: { healthy: false, version: null }
      }));
      addLog('error', `Backend error: ${error.message}`);
    }
  }, [API_URL]);

  const checkAutoTradingStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/auto-trading/status`);
      const data = response.data;
      setStatus(prev => ({
        ...prev,
        autoTrading: {
          running: data.is_running,
          scanCount: data.scan_count,
          tradesExecuted: data.trades_executed,
          lastScan: data.last_scan,
          opportunities: data.current_opportunities
        }
      }));
      if (data.is_running) {
        addLog('autotrading', `Scan #${data.scan_count} | Trades: ${data.trades_executed}`);
      }
    } catch (error) {
      addLog('error', `Auto trading status error: ${error.message}`);
    }
  }, [API_URL]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    addLog('system', 'Refreshing status...');
    
    // Update wallet status
    setStatus(prev => ({
      ...prev,
      wallet: {
        connected,
        address: publicKey?.toBase58()?.substring(0, 8) + '...',
        walletName: wallet?.adapter?.name
      }
    }));
    
    await Promise.all([
      checkRpcHealth(),
      checkBackendHealth(),
      checkAutoTradingStatus()
    ]);
    
    setLoading(false);
  }, [connected, publicKey, wallet, checkRpcHealth, checkBackendHealth, checkAutoTradingStatus]);

  useEffect(() => {
    if (isOpen) {
      refreshAll();
      const interval = setInterval(refreshAll, 5000);
      return () => clearInterval(interval);
    }
  }, [isOpen, refreshAll]);

  if (!isOpen) return null;

  const StatusIndicator = ({ healthy, label }) => (
    <div className="flex items-center gap-2">
      {healthy ? (
        <CheckCircle className="w-4 h-4 text-neon-green" />
      ) : (
        <XCircle className="w-4 h-4 text-neon-red" />
      )}
      <span className={healthy ? 'text-neon-green' : 'text-neon-red'}>{label}</span>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <Card className="bg-[#0A0A0A] border-[#1E293B] w-full max-w-2xl max-h-[80vh] overflow-hidden">
        <CardHeader className="border-b border-[#1E293B]">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-neon-cyan" />
              Debug Monitoring Panel
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
        
        <CardContent className="p-4 space-y-4">
          {/* Status Grid */}
          <div className="grid grid-cols-2 gap-4">
            {/* Wallet Status */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                <Wallet className="w-4 h-4 text-neon-cyan" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Wallet</span>
              </div>
              <StatusIndicator 
                healthy={status.wallet.connected} 
                label={status.wallet.connected ? 'Connected' : 'Disconnected'} 
              />
              {status.wallet.connected && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {status.wallet.walletName} | {status.wallet.address}
                </div>
              )}
            </div>

            {/* RPC Status */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                {status.rpc.healthy ? (
                  <Wifi className="w-4 h-4 text-neon-green" />
                ) : (
                  <WifiOff className="w-4 h-4 text-neon-red" />
                )}
                <span className="text-xs uppercase tracking-wider text-muted-foreground">RPC</span>
              </div>
              <StatusIndicator 
                healthy={status.rpc.healthy} 
                label={status.rpc.healthy ? 'Connected' : 'Disconnected'} 
              />
              {status.rpc.healthy && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Latency: {status.rpc.latency}ms
                </div>
              )}
            </div>

            {/* Backend Status */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                <Database className="w-4 h-4 text-neon-violet" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Backend</span>
              </div>
              <StatusIndicator 
                healthy={status.backend.healthy} 
                label={status.backend.healthy ? 'Healthy' : 'Offline'} 
              />
              {status.backend.healthy && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Version: {status.backend.version}
                </div>
              )}
            </div>

            {/* Auto Trading Status */}
            <div className="p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-4 h-4 text-neon-green" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Auto Trading</span>
              </div>
              <div className="flex items-center gap-2">
                {status.autoTrading.running ? (
                  <Badge className="bg-neon-green/20 text-neon-green border-none animate-pulse">
                    ACTIVE
                  </Badge>
                ) : (
                  <Badge className="bg-gray-500/20 text-gray-400 border-none">
                    STOPPED
                  </Badge>
                )}
              </div>
              {status.autoTrading.running && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Scans: {status.autoTrading.scanCount} | Trades: {status.autoTrading.tradesExecuted}
                </div>
              )}
            </div>
          </div>

          {/* Auto Trading Details */}
          {status.autoTrading.running && (
            <div className="p-3 bg-neon-green/5 border border-neon-green/20 rounded-sm">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-neon-green" />
                <span className="text-sm font-semibold text-neon-green">Auto Trading Engine Active</span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Interval:</span>
                  <span className="ml-2 font-mono">3s</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Scans:</span>
                  <span className="ml-2 font-mono text-neon-cyan">{status.autoTrading.scanCount}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Opportunities:</span>
                  <span className="ml-2 font-mono text-neon-green">{status.autoTrading.opportunities || 0}</span>
                </div>
              </div>
            </div>
          )}

          {/* Activity Log */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-muted-foreground" />
              <span className="text-xs uppercase tracking-wider text-muted-foreground">Activity Log</span>
            </div>
            <ScrollArea className="h-40 p-2 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="space-y-1 font-mono text-xs">
                {logs.length === 0 ? (
                  <div className="text-muted-foreground">No activity yet...</div>
                ) : (
                  logs.slice().reverse().map((log, idx) => (
                    <div key={idx} className="flex gap-2">
                      <span className="text-muted-foreground">[{log.time}]</span>
                      <span className={
                        log.type === 'error' ? 'text-neon-red' :
                        log.type === 'autotrading' ? 'text-neon-green' :
                        log.type === 'rpc' ? 'text-neon-cyan' :
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
        </CardContent>
      </Card>
    </div>
  );
};

// Missing import
const Wallet = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
  </svg>
);

export default DebugPanel;
