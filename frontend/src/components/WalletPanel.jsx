import React, { useState, useEffect, useCallback } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { LAMPORTS_PER_SOL } from '@solana/web3.js';
import axios from 'axios';
import { 
  Wallet, 
  Copy, 
  ExternalLink, 
  RefreshCw,
  Check,
  Coins
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { toast } from 'sonner';

const WalletPanel = () => {
  const { connected, publicKey, disconnect } = useWallet();
  const { connection } = useConnection();
  const [balance, setBalance] = useState(0);
  const [solPrice, setSolPrice] = useState(150);
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchBalance = useCallback(async () => {
    if (!connected || !publicKey || !connection) return;
    
    setLoading(true);
    try {
      const bal = await connection.getBalance(publicKey);
      setBalance(bal / LAMPORTS_PER_SOL);
      
      // Fetch token accounts
      const tokenAccounts = await connection.getParsedTokenAccountsByOwner(
        publicKey,
        { programId: new (await import('@solana/web3.js')).PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') }
      );
      
      const tokenList = tokenAccounts.value
        .map(account => {
          const info = account.account.data.parsed.info;
          return {
            mint: info.mint,
            balance: info.tokenAmount.uiAmount || 0,
            decimals: info.tokenAmount.decimals,
            symbol: info.mint.slice(0, 4) + '...'
          };
        })
        .filter(t => t.balance > 0);
      
      setTokens(tokenList);
    } catch (error) {
      console.error('Error fetching balance:', error);
    }
    setLoading(false);
  }, [connected, publicKey, connection]);

  const fetchSolPrice = useCallback(async () => {
    try {
      const response = await axios.get(
        'https://api.coingecko.com/api/v3/simple/price',
        { params: { ids: 'solana', vs_currencies: 'usd' } }
      );
      setSolPrice(response.data.solana?.usd || 150);
    } catch {
      // Use default
    }
  }, []);

  useEffect(() => {
    fetchBalance();
    fetchSolPrice();
    
    const interval = setInterval(() => {
      fetchBalance();
      fetchSolPrice();
    }, 30000);
    
    return () => clearInterval(interval);
  }, [fetchBalance, fetchSolPrice]);

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
    return `${address.slice(0, 4)}...${address.slice(-4)}`;
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
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {/* Address */}
        <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
          <div className="font-mono text-sm text-muted-foreground">
            {shortenAddress(publicKey?.toString())}
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={copyAddress}>
              {copied ? <Check className="w-3 h-3 text-neon-green" /> : <Copy className="w-3 h-3" />}
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-7 w-7"
              onClick={() => window.open(`https://solscan.io/account/${publicKey?.toString()}`, '_blank')}
            >
              <ExternalLink className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* SOL Balance */}
        <div className="p-4 bg-gradient-to-r from-neon-violet/10 to-neon-cyan/10 rounded-sm border border-[#1E293B]">
          <div className="text-xs uppercase tracking-widest text-muted-foreground mb-1">SOL Balance</div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-mono font-bold text-neon-cyan">
              {balance.toFixed(4)}
            </span>
            <span className="text-muted-foreground">SOL</span>
          </div>
          <div className="text-sm text-muted-foreground mt-1">
            ≈ ${(balance * solPrice).toFixed(2)} USD
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
                {tokens.slice(0, 5).map((token, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center justify-between p-2 bg-[#050505] rounded-sm border border-[#1E293B]"
                  >
                    <div className="font-mono text-sm">{token.symbol}</div>
                    <div className="font-mono text-sm text-neon-green">
                      {token.balance.toFixed(2)}
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
