import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useWallet } from '@solana/wallet-adapter-react';
import axios from 'axios';
import { 
  Wallet, 
  Copy, 
  ExternalLink, 
  RefreshCw,
  Check,
  Coins,
  TrendingUp,
  AlertCircle,
  Wifi,
  WifiOff
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { toast } from 'sonner';
import { useApp } from '../context/AppContext';

const WalletPanel = ({ solPrice = 150, onBalanceUpdate }) => {
  const { t } = useTranslation();
  const { connected, publicKey, disconnect, connecting, wallet } = useWallet();
  const { API_URL } = useApp();
  const [balance, setBalance] = useState(0);
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);
  const [rpcStatus, setRpcStatus] = useState({ healthy: true, endpoint: null });
  const refreshIntervalRef = useRef(null);

  // Debug logging
  useEffect(() => {
    console.log('🔌 Wallet State:', {
      connected,
      connecting,
      publicKey: publicKey?.toBase58(),
      wallet: wallet?.adapter?.name
    });
  }, [connected, connecting, publicKey, wallet]);

  // Check wallet status from backend (simple GET request)
  const checkWalletStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/wallet/status`, { timeout: 5000 });
      const data = response.data;
      
      if (data.wallet_synced && data.wallet_address) {
        console.log(`✅ Wallet status: synced - ${data.balance_sol} SOL`);
        setBalance(data.balance_sol);
        setLastUpdate(new Date(data.last_update || Date.now()));
        setRpcStatus({ healthy: true, endpoint: 'Backend RPC' });
        setError(null);
        
        if (onBalanceUpdate) {
          onBalanceUpdate(data.balance_sol);
        }
        return true;
      }
      return false;
    } catch (err) {
      console.warn('⚠️ Could not check wallet status:', err.message);
      return false;
    }
  }, [API_URL, onBalanceUpdate]);

  // Sync wallet with backend (POST request to sync and fetch balance)
  const syncWalletWithBackend = useCallback(async () => {
    if (!connected || !publicKey) {
      console.log('⚠️ Wallet not connected, skipping sync');
      setBalance(0);
      // Notify backend that wallet is disconnected
      try {
        await axios.post(`${API_URL}/wallet/disconnect`);
      } catch (e) {
        console.warn('Failed to notify backend of wallet disconnect');
      }
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const address = publicKey.toBase58();
      console.log(`📊 Syncing wallet with backend for ${address.substring(0, 8)}...`);
      
      // Use /wallet/sync to sync with trading engine
      const response = await axios.post(`${API_URL}/wallet/sync`, null, {
        params: { address },
        timeout: 15000
      });
      
      if (response.data.success) {
        const solBalance = response.data.balance;
        console.log(`✅ Wallet synced: ${solBalance} SOL - Trading engine updated`);
        
        setBalance(solBalance);
        setLastUpdate(new Date());
        setRpcStatus({ healthy: true, endpoint: 'Backend RPC' });
        
        if (onBalanceUpdate) {
          onBalanceUpdate(solBalance);
        }
        
        // Fetch tokens via backend (non-critical)
        fetchTokensViaBackend(address);
      } else {
        throw new Error(response.data.error || 'Failed to sync wallet');
      }
      
    } catch (err) {
      console.error('❌ Wallet sync error:', err.message);
      setError('Failed to sync wallet. Network unavailable.');
      setRpcStatus({ healthy: false, endpoint: null });
      
      toast.error('Wallet Sync Failed', { 
        description: 'Unable to sync wallet with trading engine.',
        action: {
          label: 'Retry',
          onClick: () => syncWalletWithBackend()
        }
      });
    } finally {
      setLoading(false);
    }
  }, [connected, publicKey, API_URL, onBalanceUpdate]);

  // Combined function: first check status, then sync if needed
  const fetchBalanceViaBackend = useCallback(async () => {
    if (!connected || !publicKey) {
      console.log('⚠️ Wallet not connected');
      setBalance(0);
      try {
        await axios.post(`${API_URL}/wallet/disconnect`);
      } catch (e) {
        // Ignore
      }
      return;
    }
    
    // First, check if wallet is already synced via simple status endpoint
    const alreadySynced = await checkWalletStatus();
    
    if (!alreadySynced) {
      // Need to sync wallet
      await syncWalletWithBackend();
    }
  }, [connected, publicKey, API_URL, checkWalletStatus, syncWalletWithBackend]);

  // Fetch tokens via Backend API
  const fetchTokensViaBackend = async (address) => {
    try {
      const response = await axios.get(`${API_URL}/wallet/tokens`, {
        params: { address },
        timeout: 15000
      });
      
      if (response.data.success) {
        const tokenList = response.data.tokens.map(t => ({
          mint: t.mint,
          balance: t.balance,
          decimals: t.decimals,
          symbol: t.mint.slice(0, 4) + '...' + t.mint.slice(-4)
        }));
        
        setTokens(tokenList);
        console.log(`📦 Found ${tokenList.length} tokens via backend`);
      }
    } catch (tokenError) {
      console.warn('⚠️ Error fetching tokens (non-critical):', tokenError.message);
    }
  };

  // Fetch balance on wallet connect and every 10 seconds
  useEffect(() => {
    if (connected && publicKey) {
      console.log('🔄 Wallet connected, fetching balance via backend...');
      fetchBalanceViaBackend();
      
      // Set up 10-second refresh interval
      refreshIntervalRef.current = setInterval(() => {
        fetchBalanceViaBackend();
      }, 10000);
      
      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
        }
      };
    } else {
      // Reset state when disconnected
      setBalance(0);
      setTokens([]);
      setError(null);
      setRpcStatus({ healthy: true, endpoint: null });
    }
  }, [connected, publicKey, fetchBalanceViaBackend]);

  const copyAddress = async () => {
    if (publicKey) {
      try {
        await navigator.clipboard.writeText(publicKey.toBase58());
        setCopied(true);
        toast.success(t('wallet.addressCopied'));
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        toast.error(t('errors.somethingWentWrong'));
      }
    }
  };

  const shortenAddress = (address) => {
    if (!address) return '';
    const str = typeof address === 'string' ? address : address.toBase58();
    return `${str.slice(0, 6)}...${str.slice(-4)}`;
  };

  const openSolscan = () => {
    if (publicKey) {
      window.open(`https://solscan.io/account/${publicKey.toBase58()}`, '_blank');
    }
  };

  // Not connected state - show 0 values
  if (!connected && !connecting) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="wallet-panel-disconnected">
        <CardHeader className="border-b border-[#1E293B] pb-3">
          <div className="flex items-center gap-2">
            <Wallet className="w-5 h-5 text-muted-foreground" />
            <CardTitle className="font-heading text-base">{t('wallet.title')}</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {/* SOL Balance - Show 0 when disconnected */}
          <div className="p-4 bg-gradient-to-r from-neon-violet/10 to-neon-cyan/10 rounded-sm border border-[#1E293B]">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs uppercase tracking-widest text-muted-foreground">{t('wallet.solBalance')}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-mono font-bold text-muted-foreground" data-testid="sol-balance">
                0.00
              </span>
              <span className="text-muted-foreground">SOL</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm text-muted-foreground" data-testid="usd-value">
                ≈ $0.00 USD
              </span>
            </div>
          </div>
          <p className="text-muted-foreground text-center text-sm">{t('wallet.connectToTrade')}</p>
        </CardContent>
      </Card>
    );
  }

  // Connecting state
  if (connecting) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="wallet-panel-connecting">
        <CardContent className="p-6 text-center">
          <RefreshCw className="w-12 h-12 mx-auto mb-4 text-neon-cyan animate-spin" />
          <p className="text-muted-foreground">{t('wallet.connecting')}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="wallet-panel">
      <CardHeader className="border-b border-[#1E293B] pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wallet className="w-5 h-5 text-neon-cyan" />
            <CardTitle className="font-heading text-base">{t('wallet.title')}</CardTitle>
            <Badge className="bg-neon-green/20 text-neon-green border-none text-xs">
              {wallet?.adapter?.name || t('wallet.connected')}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            {/* RPC Status Indicator */}
            <div className="flex items-center gap-1" title={rpcStatus.endpoint || t('wallet.backendRpc')}>
              {rpcStatus.healthy ? (
                <Wifi className="w-3 h-3 text-neon-green" />
              ) : (
                <WifiOff className="w-3 h-3 text-neon-red" />
              )}
            </div>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => fetchBalanceViaBackend()}
              disabled={loading}
              data-testid="refresh-balance"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {/* Address */}
        <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
          <div className="font-mono text-sm text-neon-cyan" data-testid="wallet-address">
            {publicKey ? shortenAddress(publicKey) : t('common.loading')}
          </div>
          <div className="flex items-center gap-1">
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-7 w-7" 
              onClick={copyAddress}
              data-testid="copy-address"
              disabled={!publicKey}
            >
              {copied ? <Check className="w-3 h-3 text-neon-green" /> : <Copy className="w-3 h-3" />}
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-7 w-7"
              onClick={openSolscan}
              data-testid="view-solscan"
              disabled={!publicKey}
            >
              <ExternalLink className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="flex items-center gap-2 p-2 bg-neon-red/10 border border-neon-red/30 rounded-sm">
            <AlertCircle className="w-4 h-4 text-neon-red flex-shrink-0" />
            <div className="flex-1">
              <span className="text-xs text-neon-red">{error}</span>
              <Button 
                variant="link" 
                size="sm" 
                className="text-xs text-neon-cyan p-0 h-auto ml-2"
                onClick={() => fetchBalanceViaBackend()}
              >
                {t('common.retry')}
              </Button>
            </div>
          </div>
        )}

        {/* RPC Status Info */}
        {rpcStatus.endpoint && !error && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Wifi className="w-3 h-3" />
            <span>{t('wallet.backendRpc')}: {rpcStatus.endpoint}</span>
          </div>
        )}

        {/* SOL Balance */}
        <div className="p-4 bg-gradient-to-r from-neon-violet/10 to-neon-cyan/10 rounded-sm border border-[#1E293B]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">{t('wallet.solBalance')}</span>
            {lastUpdate && (
              <span className="text-xs text-muted-foreground">
                {lastUpdate.toLocaleTimeString()}
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-mono font-bold text-neon-cyan" data-testid="sol-balance">
              {loading && balance === 0 ? '...' : balance.toFixed(4)}
            </span>
            <span className="text-muted-foreground">SOL</span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <TrendingUp className="w-3 h-3 text-neon-green" />
            <span className="text-sm text-neon-green" data-testid="usd-value">
              ≈ ${(balance * solPrice).toFixed(2)} USD
            </span>
          </div>
        </div>

        {/* Token Holdings */}
        {tokens.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Coins className="w-4 h-4 text-neon-violet" />
              <span className="text-xs uppercase tracking-widest text-muted-foreground">
                {t('wallet.tokenHoldings')} ({tokens.length})
              </span>
            </div>
            <ScrollArea className="h-32">
              <div className="space-y-2">
                {tokens.slice(0, 10).map((token, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center justify-between p-2 bg-[#050505] rounded-sm border border-[#1E293B] cursor-pointer hover:border-neon-cyan/50 transition-colors"
                    onClick={() => window.open(`https://solscan.io/token/${token.mint}`, '_blank')}
                  >
                    <div className="font-mono text-xs text-muted-foreground">{token.symbol}</div>
                    <div className="font-mono text-sm text-neon-green">
                      {token.balance < 0.01 ? token.balance.toExponential(2) : token.balance.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* Disconnect */}
        <Button 
          variant="outline" 
          className="w-full border-neon-red/30 text-neon-red hover:bg-neon-red/10"
          onClick={disconnect}
          data-testid="disconnect-wallet"
        >
          {t('wallet.disconnectWallet')}
        </Button>
      </CardContent>
    </Card>
  );
};

export default WalletPanel;
