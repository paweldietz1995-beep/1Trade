import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { LAMPORTS_PER_SOL, PublicKey, Connection } from '@solana/web3.js';
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
import { useRPC } from '../context/SolanaWalletProvider';

const TOKEN_PROGRAM_ID = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');

// RPC Endpoints for failover - ordered by reliability
const RPC_ENDPOINTS = [
  'https://rpc.ankr.com/solana',           // Primary: Ankr (reliable, no rate limiting)
  'https://api.mainnet-beta.solana.com'    // Fallback: Solana Mainnet
];

const WalletPanel = ({ solPrice = 150, onBalanceUpdate }) => {
  const { connected, publicKey, disconnect, connecting, wallet } = useWallet();
  const { connection } = useConnection();
  const rpcContext = useRPC();
  const [balance, setBalance] = useState(0);
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);
  const [rpcStatus, setRpcStatus] = useState({ healthy: true, endpoint: null, retries: 0 });
  const refreshIntervalRef = useRef(null);
  const currentEndpointIndexRef = useRef(0);

  // Debug logging
  useEffect(() => {
    console.log('🔌 Wallet State:', {
      connected,
      connecting,
      publicKey: publicKey?.toBase58(),
      wallet: wallet?.adapter?.name,
      rpcEndpoint: rpcContext?.currentEndpoint?.substring(0, 30)
    });
  }, [connected, connecting, publicKey, wallet, rpcContext]);

  // Create connection with specific endpoint
  const createConnection = useCallback((endpointIndex) => {
    const endpoint = RPC_ENDPOINTS[endpointIndex];
    console.log(`🔗 Creating connection to: ${endpoint.substring(0, 40)}...`);
    return new Connection(endpoint, {
      commitment: 'confirmed',
      confirmTransactionInitialTimeout: 15000
    });
  }, []);

  // Fetch balance with automatic failover
  const fetchBalanceWithFailover = useCallback(async (maxRetries = 3) => {
    if (!connected || !publicKey) {
      console.log('⚠️ Wallet not connected, skipping balance fetch');
      setBalance(0);
      return;
    }
    
    setLoading(true);
    setError(null);
    
    let lastError = null;
    
    // Try each endpoint with retries
    for (let endpointIndex = 0; endpointIndex < RPC_ENDPOINTS.length; endpointIndex++) {
      const endpoint = RPC_ENDPOINTS[endpointIndex];
      
      for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
          console.log(`📊 Fetching balance - Endpoint ${endpointIndex + 1}/${RPC_ENDPOINTS.length}, Attempt ${attempt + 1}/${maxRetries}`);
          
          // Create a fresh connection for this attempt
          const conn = createConnection(endpointIndex);
          
          // Fetch SOL balance with timeout
          const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('RPC timeout (10s)')), 10000)
          );
          
          const balancePromise = conn.getBalance(publicKey);
          const lamports = await Promise.race([balancePromise, timeoutPromise]);
          
          const solBalance = lamports / LAMPORTS_PER_SOL;
          console.log(`✅ Balance fetched: ${solBalance} SOL from ${endpoint.substring(0, 30)}...`);
          
          setBalance(solBalance);
          setLastUpdate(new Date());
          setRpcStatus({ healthy: true, endpoint: endpoint, retries: 0 });
          currentEndpointIndexRef.current = endpointIndex;
          
          // Notify parent component
          if (onBalanceUpdate) {
            onBalanceUpdate(solBalance);
          }
          
          // Fetch SPL tokens (non-critical, don't fail on error)
          fetchTokens(conn);
          
          setLoading(false);
          return; // Success!
          
        } catch (err) {
          lastError = err;
          console.warn(`❌ Balance fetch error (Endpoint ${endpointIndex + 1}, Attempt ${attempt + 1}):`, err.message);
          
          // Small delay before retry
          if (attempt < maxRetries - 1) {
            await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
          }
        }
      }
      
      // This endpoint failed all retries, try next
      console.log(`⚠️ Endpoint ${endpointIndex + 1} (${endpoint.substring(0, 30)}) failed, trying next...`);
    }
    
    // All endpoints failed
    console.error('❌ All RPC endpoints failed:', lastError);
    setError('Failed to fetch balance. All RPC endpoints unavailable.');
    setRpcStatus({ healthy: false, endpoint: null, retries: maxRetries * RPC_ENDPOINTS.length });
    toast.error('RPC Connection Failed', { 
      description: 'Unable to connect to Solana network. Please try again.',
      action: {
        label: 'Retry',
        onClick: () => fetchBalanceWithFailover()
      }
    });
    
    setLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, publicKey, createConnection, onBalanceUpdate]);

  // Fetch SPL tokens (separate function, non-blocking)
  const fetchTokens = async (conn) => {
    if (!publicKey) return;
    
    try {
      const tokenAccounts = await conn.getParsedTokenAccountsByOwner(
        publicKey,
        { programId: TOKEN_PROGRAM_ID }
      );
      
      const tokenList = tokenAccounts.value
        .map(account => {
          const info = account.account.data.parsed.info;
          return {
            mint: info.mint,
            balance: info.tokenAmount.uiAmount || 0,
            decimals: info.tokenAmount.decimals,
            symbol: info.mint.slice(0, 4) + '...' + info.mint.slice(-4)
          };
        })
        .filter(t => t.balance > 0)
        .sort((a, b) => b.balance - a.balance);
      
      setTokens(tokenList);
      console.log(`📦 Found ${tokenList.length} tokens`);
    } catch (tokenError) {
      console.warn('⚠️ Error fetching tokens (non-critical):', tokenError.message);
    }
  };

  // Fetch balance on wallet connect and every 10 seconds
  useEffect(() => {
    if (connected && publicKey) {
      console.log('🔄 Wallet connected, fetching balance...');
      fetchBalanceWithFailover();
      
      // Set up 10-second refresh interval
      refreshIntervalRef.current = setInterval(() => {
        fetchBalanceWithFailover();
      }, 10000);
      
      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
        }
      };
    } else {
      setBalance(0);
      setTokens([]);
      setError(null);
      setRpcStatus({ healthy: true, endpoint: null, retries: 0 });
    }
  }, [connected, publicKey, fetchBalanceWithFailover]);

  const copyAddress = async () => {
    if (publicKey) {
      try {
        await navigator.clipboard.writeText(publicKey.toBase58());
        setCopied(true);
        toast.success('Address copied to clipboard!');
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        toast.error('Failed to copy address');
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

  // Not connected state
  if (!connected && !connecting) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="wallet-panel-disconnected">
        <CardContent className="p-6 text-center">
          <Wallet className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground mb-2">Connect your wallet to start trading</p>
          <p className="text-xs text-muted-foreground">Supports Phantom, Solflare, and more</p>
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
          <p className="text-muted-foreground">Connecting to wallet...</p>
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
            <CardTitle className="font-heading text-base">Wallet</CardTitle>
            <Badge className="bg-neon-green/20 text-neon-green border-none text-xs">
              {wallet?.adapter?.name || 'Connected'}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            {/* RPC Status Indicator */}
            <div className="flex items-center gap-1" title={rpcStatus.endpoint || 'No connection'}>
              {rpcStatus.healthy ? (
                <Wifi className="w-3 h-3 text-neon-green" />
              ) : (
                <WifiOff className="w-3 h-3 text-neon-red" />
              )}
            </div>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => fetchBalanceWithFailover()}
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
            {publicKey ? shortenAddress(publicKey) : 'Loading...'}
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
                onClick={() => fetchBalanceWithFailover()}
              >
                Retry
              </Button>
            </div>
          </div>
        )}

        {/* RPC Status Info */}
        {rpcStatus.endpoint && !error && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Wifi className="w-3 h-3" />
            <span>RPC: {rpcStatus.endpoint.includes('ankr') ? 'Ankr' : 'Solana Mainnet'}</span>
          </div>
        )}

        {/* SOL Balance */}
        <div className="p-4 bg-gradient-to-r from-neon-violet/10 to-neon-cyan/10 rounded-sm border border-[#1E293B]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">SOL Balance</span>
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
                Token Holdings ({tokens.length})
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
          Disconnect Wallet
        </Button>
      </CardContent>
    </Card>
  );
};

export default WalletPanel;
