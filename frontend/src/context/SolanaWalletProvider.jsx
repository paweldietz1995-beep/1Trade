import React, { useMemo, createContext, useContext, useState } from 'react';
import { ConnectionProvider, WalletProvider } from '@solana/wallet-adapter-react';
import { WalletAdapterNetwork } from '@solana/wallet-adapter-base';
import { WalletModalProvider } from '@solana/wallet-adapter-react-ui';
import { PhantomWalletAdapter, SolflareWalletAdapter } from '@solana/wallet-adapter-wallets';
import '@solana/wallet-adapter-react-ui/styles.css';

// Minimal RPC endpoint for wallet adapter (used only for wallet connection, not data fetching)
// All balance/token fetching goes through Backend RPC to avoid CORS/rate-limiting issues
const WALLET_RPC_ENDPOINT = 'https://api.mainnet-beta.solana.com';

// RPC Context - simplified since all RPC calls go through backend
const RPCContext = createContext(null);

export const useRPC = () => {
  const context = useContext(RPCContext);
  if (!context) {
    throw new Error('useRPC must be used within SolanaWalletProvider');
  }
  return context;
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
        <WalletProvider wallets={wallets} autoConnect>
          <WalletModalProvider>
            {children}
          </WalletModalProvider>
        </WalletProvider>
      </ConnectionProvider>
    </RPCContext.Provider>
  );
};

export default SolanaWalletProvider;
