import React, { useMemo, createContext, useContext, useState, useCallback } from 'react';
import { ConnectionProvider, WalletProvider } from '@solana/wallet-adapter-react';
import { WalletAdapterNetwork } from '@solana/wallet-adapter-base';
import { WalletModalProvider } from '@solana/wallet-adapter-react-ui';
import { PhantomWalletAdapter, SolflareWalletAdapter } from '@solana/wallet-adapter-wallets';
import { Connection } from '@solana/web3.js';
import '@solana/wallet-adapter-react-ui/styles.css';

// RPC Endpoints with failover support
// Primary: Ankr (reliable, no rate limiting)
// Fallback: Solana Mainnet
const RPC_ENDPOINTS = [
  'https://rpc.ankr.com/solana',
  'https://api.mainnet-beta.solana.com'
];

// RPC Context for failover management
const RPCContext = createContext(null);

export const useRPC = () => {
  const context = useContext(RPCContext);
  if (!context) {
    throw new Error('useRPC must be used within SolanaWalletProvider');
  }
  return context;
};

// Custom connection with retry and failover
export const createConnectionWithRetry = async (endpoints = RPC_ENDPOINTS, timeout = 10000) => {
  for (let i = 0; i < endpoints.length; i++) {
    const endpoint = endpoints[i];
    try {
      console.log(`🔌 Trying RPC endpoint ${i + 1}/${endpoints.length}: ${endpoint.substring(0, 30)}...`);
      const connection = new Connection(endpoint, {
        commitment: 'confirmed',
        confirmTransactionInitialTimeout: timeout
      });
      
      // Test connection with a simple call
      const startTime = Date.now();
      await Promise.race([
        connection.getSlot(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), timeout))
      ]);
      const latency = Date.now() - startTime;
      
      console.log(`✅ RPC connected: ${endpoint.substring(0, 30)}... (${latency}ms)`);
      return { connection, endpoint, latency };
    } catch (error) {
      console.warn(`⚠️ RPC endpoint ${i + 1} failed:`, error.message);
      if (i === endpoints.length - 1) {
        throw new Error('All RPC endpoints failed');
      }
    }
  }
  throw new Error('No RPC endpoints available');
};

export const SolanaWalletProvider = ({ children }) => {
  const network = WalletAdapterNetwork.Mainnet;
  const [currentEndpointIndex, setCurrentEndpointIndex] = useState(0);
  const [rpcStatus, setRpcStatus] = useState({ connected: false, endpoint: null, latency: null });
  
  // Primary endpoint with fallback
  const endpoint = useMemo(() => {
    const envRpc = process.env.REACT_APP_SOLANA_RPC;
    if (envRpc) {
      console.log('🔧 Using custom RPC from env:', envRpc.substring(0, 30));
      return envRpc;
    }
    return RPC_ENDPOINTS[currentEndpointIndex];
  }, [currentEndpointIndex]);

  // Switch to next endpoint on failure
  const switchToNextEndpoint = useCallback(() => {
    setCurrentEndpointIndex((prev) => {
      const next = (prev + 1) % RPC_ENDPOINTS.length;
      console.log(`🔄 Switching to RPC endpoint ${next + 1}: ${RPC_ENDPOINTS[next].substring(0, 30)}...`);
      return next;
    });
  }, []);

  // RPC context value
  const rpcContextValue = useMemo(() => ({
    endpoints: RPC_ENDPOINTS,
    currentEndpoint: endpoint,
    currentEndpointIndex,
    switchToNextEndpoint,
    rpcStatus,
    setRpcStatus
  }), [endpoint, currentEndpointIndex, switchToNextEndpoint, rpcStatus]);

  const wallets = useMemo(
    () => [
      new PhantomWalletAdapter(),
      new SolflareWalletAdapter(),
    ],
    []
  );

  // Connection config for better reliability
  const connectionConfig = useMemo(() => ({
    commitment: 'confirmed',
    confirmTransactionInitialTimeout: 60000,
    disableRetryOnRateLimit: false
  }), []);

  console.log('🌐 SolanaWalletProvider initialized with endpoint:', endpoint.substring(0, 40));

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
