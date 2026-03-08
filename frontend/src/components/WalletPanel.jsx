import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { LAMPORTS_PER_SOL, PublicKey } from '@solana/web3.js';
import { 
  Wallet, 
  Copy, 
  ExternalLink, 
  RefreshCw,
  Check,
  Coins,
  TrendingUp
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { toast } from 'sonner';

const TOKEN_PROGRAM_ID = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');

const WalletPanel = ({ solPrice = 150 }) => {
  const { connected, publicKey, disconnect } = useWallet();
  const { connection } = useConnection();
  const [balance, setBalance] = useState(0);
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const refreshIntervalRef = useRef(null);

  const fetchBalance = useCallback(async () => {
    if (!connected || !publicKey || !connection) {
      setBalance(0);
      return;
    }
    
    setLoading(true);
    try {
      // Fetch SOL balance using Solana RPC
      const lamports = await connection.getBalance(publicKey);
      const solBalance = lamports / LAMPORTS_PER_SOL;
      setBalance(solBalance);
      setLastUpdate(new Date());
      
      // Fetch SPL token accounts
      try {
        const tokenAccounts = await connection.getParsedTokenAccountsByOwner(
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
      } catch (tokenError) {
        console.error('Error fetching tokens:', tokenError);
      }
    } catch (error) {
      console.error('Error fetching balance:', error);
      toast.error('Failed to fetch wallet balance');
    }
    setLoading(false);
  }, [connected, publicKey, connection]);

  // Auto refresh every 10 seconds when connected
  useEffect(() => {
    if (connected && publicKey) {
      // Immediate fetch on connect
      fetchBalance();
      
      // Set up 10-second refresh interval
      refreshIntervalRef.current = setInterval(fetchBalance, 10000);
      
      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
        }
      };
    } else {
      setBalance(0);
      setTokens([]);
    }
  }, [connected, publicKey, fetchBalance]);

  const copyAddress = async () => {
    if (publicKey) {
      await navigator.clipboard.writeText(publicKey.toString());
      setCopied(true);
      toast.success('Address copied!');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const shortenAddress = (address) => {
    if (!address) return '';
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  const openSolscan = () => {
    if (publicKey) {
      window.open(`https://solscan.io/account/${publicKey.toString()}`, '_blank');
    }
  };

  if (!connected) {
    return (
      <Card className="bg-[#0A0A0A] border-[#1E293B]" data-testid="wallet-panel-disconnected">
        <CardContent className="p-6 text-center">
          <Wallet className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground mb-4">Connect your wallet to start trading</p>
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
              Connected
            </Badge>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={fetchBalance}
            disabled={loading}
            data-testid="refresh-balance"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {/* Address */}
        <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
          <div className="font-mono text-sm text-neon-cyan" data-testid="wallet-address">
            {shortenAddress(publicKey?.toString())}
          </div>
          <div className="flex items-center gap-1">
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-7 w-7" 
              onClick={copyAddress}
              data-testid="copy-address"
            >
              {copied ? <Check className="w-3 h-3 text-neon-green" /> : <Copy className="w-3 h-3" />}
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-7 w-7"
              onClick={openSolscan}
              data-testid="view-solscan"
            >
              <ExternalLink className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* SOL Balance */}
        <div className="p-4 bg-gradient-to-r from-neon-violet/10 to-neon-cyan/10 rounded-sm border border-[#1E293B]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">SOL Balance</span>
            {lastUpdate && (
              <span className="text-xs text-muted-foreground">
                Updated {lastUpdate.toLocaleTimeString()}
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-mono font-bold text-neon-cyan" data-testid="sol-balance">
              {balance.toFixed(4)}
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
