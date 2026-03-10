import React, { useMemo, createContext, useContext, useState, useCallback } from 'react';
import { ConnectionProvider, WalletProvider, useWallet } from '@solana/wallet-adapter-react';
import { WalletAdapterNetwork } from '@solana/wallet-adapter-base';
import { WalletModalProvider, useWalletModal } from '@solana/wallet-adapter-react-ui';
import { PhantomWalletAdapter, SolflareWalletAdapter } from '@solana/wallet-adapter-wallets';
import '@solana/wallet-adapter-react-ui/styles.css';

// Minimal RPC endpoint for wallet adapter (used only for wallet connection, not data fetching)
// All balance/token fetching goes through Backend RPC to avoid CORS/rate-limiting issues
const WALLET_RPC_ENDPOINT = 'https://api.mainnet-beta.solana.com';

// RPC Context - simplified since all RPC calls go through backend
const RPCContext = createContext(null);

// Wallet Change Context - for handling wallet switching
const WalletChangeContext = createContext(null);

export const useRPC = () => {
  const context = useContext(RPCContext);
  if (!context) {
    throw new Error('useRPC must be used within SolanaWalletProvider');
  }
  return context;
};

export const useWalletChange = () => {
  const context = useContext(WalletChangeContext);
  if (!context) {
    throw new Error('useWalletChange must be used within SolanaWalletProvider');
  }
  return context;
};

// Inner component to handle wallet change logic
const WalletChangeProvider = ({ children }) => {
  const { disconnect, wallet } = useWallet();
  const { setVisible } = useWalletModal();
  const [isChangingWallet, setIsChangingWallet] = useState(false);

  const changeWallet = useCallback(async () => {
    console.log('🔄 Starting wallet change process...');
    setIsChangingWallet(true);
    
    try {
      // 1. Disconnect current wallet
      if (wallet) {
        console.log('📤 Disconnecting current wallet:', wallet.adapter?.name);
        await disconnect();
      }
      
      // 2. Clear ALL localStorage wallet data
      const keysToRemove = [
        'walletName',
        'walletAdapter', 
        'connectedWallet',
        'walletAddress',
        'phantom.lastUsedAccount',
        'phantom.autoConnect',
        'solflare.autoConnect'
      ];
      
      keysToRemove.forEach(key => {
        localStorage.removeItem(key);
        sessionStorage.removeItem(key);
      });
      
      // Also clear any keys that contain 'wallet' (case insensitive)
      Object.keys(localStorage).forEach(key => {
        if (key.toLowerCase().includes('wallet')) {
          localStorage.removeItem(key);
        }
      });
      Object.keys(sessionStorage).forEach(key => {
        if (key.toLowerCase().includes('wallet')) {
          sessionStorage.removeItem(key);
        }
      });
      
      console.log('🧹 Cleared all wallet cache data');
      
      // 3. Small delay to ensure disconnect is complete
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // 4. Open wallet selection modal
      console.log('📱 Opening wallet selection modal...');
      setVisible(true);
      
    } catch (error) {
      console.error('❌ Error during wallet change:', error);
    } finally {
      setIsChangingWallet(false);
    }
  }, [disconnect, wallet, setVisible]);

  const contextValue = useMemo(() => ({
    changeWallet,
    isChangingWallet
  }), [changeWallet, isChangingWallet]);

  return (
    <WalletChangeContext.Provider value={contextValue}>
      {children}
    </WalletChangeContext.Provider>
  );
};

export const SolanaWalletProvider = ({ children }) => {
  const network = WalletAdapterNetwork.Mainnet;
  const [rpcStatus, setRpcStatus] = useState({ 
    connected: false, 
    endpoint: null, 
    note: 'Balance fetched via backend' 
  });
  
  // Endpoint for wallet adapter (minimal usage)
  const endpoint = useMemo(() => {
    const envRpc = process.env.REACT_APP_SOLANA_RPC;
    if (envRpc) {
      console.log('🔧 Using custom RPC from env:', envRpc.substring(0, 30));
      return envRpc;
    }
    return WALLET_RPC_ENDPOINT;
  }, []);

  // RPC context value - indicates that backend handles RPC
  const rpcContextValue = useMemo(() => ({
    currentEndpoint: endpoint,
    rpcStatus,
    setRpcStatus,
    note: 'All RPC calls are handled by backend for reliability'
  }), [endpoint, rpcStatus]);

  const wallets = useMemo(
    () => [
      new PhantomWalletAdapter(),
      new SolflareWalletAdapter(),
    ],
    []
  );

  // Connection config for wallet adapter
  const connectionConfig = useMemo(() => ({
    commitment: 'confirmed',
    confirmTransactionInitialTimeout: 60000,
    disableRetryOnRateLimit: false
  }), []);

  console.log('🌐 SolanaWalletProvider initialized - Backend handles all RPC calls');

  return (
    <RPCContext.Provider value={rpcContextValue}>
      <ConnectionProvider endpoint={endpoint} config={connectionConfig}>
        <WalletProvider wallets={wallets} autoConnect={false}>
          <WalletModalProvider>
            <WalletChangeProvider>
              {children}
            </WalletChangeProvider>
          </WalletModalProvider>
        </WalletProvider>
      </ConnectionProvider>
    </RPCContext.Provider>
  );
};

export default SolanaWalletProvider;
