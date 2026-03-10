import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Direct Phantom Wallet Context - bypasses wallet-adapter for simpler, more reliable connection
const PhantomWalletContext = createContext(null);

export const usePhantomWallet = () => {
  const context = useContext(PhantomWalletContext);
  if (!context) {
    throw new Error('usePhantomWallet must be used within PhantomWalletProvider');
  }
  return context;
};

export const PhantomWalletProvider = ({ children }) => {
  const [walletAddress, setWalletAddress] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [provider, setProvider] = useState(null);
  const [error, setError] = useState(null);
  const [backendSynced, setBackendSynced] = useState(false);
  const [tradingEngineReady, setTradingEngineReady] = useState(false);

  // Sync wallet with backend trading engine
  const syncWithBackend = useCallback(async (address) => {
    if (!address) {
      console.log('⚠️ No address to sync');
      return { success: false, error: 'No address provided' };
    }
    
    try {
      console.log('🔄 Syncing wallet with backend:', address);
      
      // Send wallet address in JSON body as per user requirement
      const response = await fetch(`${API_URL}/api/wallet/sync`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          wallet: address,
          force: true
        })
      });
      
      const data = await response.json();
      console.log('📡 Backend sync response:', data);
      
      if (data.success) {
        setBackendSynced(true);
        console.log('✅ Wallet synced with backend trading engine');
        
        // Automatically start trading engine if conditions are met
        await autoStartTradingEngine();
        
        return { success: true, data };
      } else {
        console.error('❌ Backend sync failed:', data.error);
        setBackendSynced(false);
        return { success: false, error: data.error };
      }
    } catch (err) {
      console.error('❌ Backend sync error:', err);
      setBackendSynced(false);
      return { success: false, error: err.message };
    }
  }, []);

  // Auto-start trading engine when wallet is synced
  const autoStartTradingEngine = useCallback(async () => {
    try {
      console.log('🚀 Checking if trading engine can start...');
      
      // First check if we can start
      const canTradeResponse = await fetch(`${API_URL}/api/wallet/can-trade`);
      const canTradeData = await canTradeResponse.json();
      console.log('📊 Can trade status:', canTradeData);
      
      if (!canTradeData.can_start) {
        console.log('⚠️ Cannot start trading:', canTradeData.reason);
        return { success: false, reason: canTradeData.reason };
      }
      
      // Check current trading status
      const statusResponse = await fetch(`${API_URL}/api/auto-trading/status`);
      const statusData = await statusResponse.json();
      
      if (statusData.is_running) {
        console.log('✅ Trading engine already running');
        setTradingEngineReady(true);
        return { success: true, already_running: true };
      }
      
      // Start the trading engine
      console.log('🔥 Starting trading engine...');
      const startResponse = await fetch(`${API_URL}/api/auto-trading/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      const startData = await startResponse.json();
      console.log('📡 Trading engine start response:', startData);
      
      if (startData.success || startData.is_running) {
        setTradingEngineReady(true);
        console.log('✅ Trading engine started successfully');
        return { success: true, data: startData };
      } else {
        console.error('❌ Failed to start trading engine:', startData.error);
        return { success: false, error: startData.error };
      }
    } catch (err) {
      console.error('❌ Error starting trading engine:', err);
      return { success: false, error: err.message };
    }
  }, []);

  // Disconnect from backend
  const disconnectFromBackend = useCallback(async () => {
    try {
      console.log('📤 Disconnecting wallet from backend...');
      
      const response = await fetch(`${API_URL}/api/wallet/disconnect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      const data = await response.json();
      console.log('📡 Backend disconnect response:', data);
      
      setBackendSynced(false);
      setTradingEngineReady(false);
      
      return { success: true };
    } catch (err) {
      console.error('❌ Backend disconnect error:', err);
      setBackendSynced(false);
      setTradingEngineReady(false);
      return { success: false, error: err.message };
    }
  }, []);

  // Check for Phantom on mount
  useEffect(() => {
    const checkPhantom = () => {
      if (typeof window !== 'undefined') {
        const phantomProvider = window.solana;
        
        if (phantomProvider?.isPhantom) {
          console.log('✅ Phantom wallet detected');
          setProvider(phantomProvider);
          
          // Listen for account changes
          phantomProvider.on('accountChanged', (publicKey) => {
            if (publicKey) {
              console.log('🔄 Account changed:', publicKey.toString());
              setWalletAddress(publicKey.toString());
              setIsConnected(true);
            } else {
              console.log('📤 Wallet disconnected via Phantom');
              handleDisconnect();
            }
          });
          
          // Listen for disconnect
          phantomProvider.on('disconnect', () => {
            console.log('📤 Phantom disconnected');
            handleDisconnect();
          });
          
          // DO NOT auto-connect - user must click connect
          // This prevents the "stuck connecting" issue
        } else {
          console.log('⚠️ Phantom wallet not found');
        }
      }
    };
    
    // Small delay to ensure window.solana is available
    const timer = setTimeout(checkPhantom, 100);
    return () => clearTimeout(timer);
  }, []);

  // Internal disconnect handler
  const handleDisconnect = useCallback(async () => {
    setWalletAddress(null);
    setIsConnected(false);
    setIsConnecting(false);
    
    // Notify backend about disconnect
    await disconnectFromBackend();
    
    // Clear all wallet-related storage
    const keysToRemove = [
      'walletAddress',
      'connectedWallet',
      'phantomWallet',
      'walletName'
    ];
    keysToRemove.forEach(key => {
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
    });
    
    // Clear any key containing 'wallet'
    Object.keys(localStorage).forEach(key => {
      if (key.toLowerCase().includes('wallet')) {
        localStorage.removeItem(key);
      }
    });
  }, [disconnectFromBackend]);

  // Connect wallet - called when user clicks "Connect Wallet"
  const connectWallet = useCallback(async () => {
    console.log('🔌 Connect wallet called');
    setError(null);
    
    try {
      const phantomProvider = window.solana;
      
      if (!phantomProvider || !phantomProvider.isPhantom) {
        const errorMsg = 'Phantom Wallet nicht installiert. Bitte installieren Sie Phantom von phantom.app';
        setError(errorMsg);
        window.open('https://phantom.app/', '_blank');
        return { success: false, error: errorMsg };
      }
      
      setIsConnecting(true);
      
      // Connect without onlyIfTrusted to force popup
      console.log('📱 Requesting Phantom connection...');
      const response = await phantomProvider.connect();
      
      if (response.publicKey) {
        const address = response.publicKey.toString();
        console.log('✅ Connected to wallet:', address);
        
        setWalletAddress(address);
        setIsConnected(true);
        setProvider(phantomProvider);
        
        // Store in localStorage for display purposes only (not for auto-connect)
        localStorage.setItem('lastConnectedWallet', address);
        
        // CRITICAL: Sync with backend trading engine
        console.log('🔄 Syncing with backend trading engine...');
        const syncResult = await syncWithBackend(address);
        
        if (syncResult.success) {
          console.log('✅ Full wallet sync complete - trading engine ready');
        } else {
          console.warn('⚠️ Backend sync failed, but wallet is connected:', syncResult.error);
        }
        
        return { success: true, address, backendSynced: syncResult.success };
      }
      
    } catch (err) {
      console.error('❌ Connection error:', err);
      
      // Handle user rejection
      if (err.code === 4001) {
        setError('Verbindung vom Benutzer abgelehnt');
      } else {
        setError(err.message || 'Verbindung fehlgeschlagen');
      }
      
      return { success: false, error: err.message };
    } finally {
      setIsConnecting(false);
    }
  }, [syncWithBackend]);

  // Disconnect wallet
  const disconnectWallet = useCallback(async () => {
    console.log('📤 Disconnect wallet called');
    
    try {
      const phantomProvider = window.solana;
      
      if (phantomProvider && phantomProvider.isConnected) {
        await phantomProvider.disconnect();
      }
      
      handleDisconnect();
      console.log('✅ Wallet disconnected successfully');
      
      return { success: true };
    } catch (err) {
      console.error('❌ Disconnect error:', err);
      // Force disconnect state even on error
      handleDisconnect();
      return { success: false, error: err.message };
    }
  }, [handleDisconnect]);

  // Change wallet - disconnect and show new wallet selector
  const changeWallet = useCallback(async () => {
    console.log('🔄 Change wallet called');
    setError(null);
    
    try {
      const phantomProvider = window.solana;
      
      if (!phantomProvider || !phantomProvider.isPhantom) {
        setError('Phantom Wallet nicht gefunden');
        return { success: false, error: 'Phantom not found' };
      }
      
      setIsConnecting(true);
      
      // Step 1: Fully disconnect current session
      if (phantomProvider.isConnected) {
        console.log('📤 Disconnecting current wallet...');
        await phantomProvider.disconnect();
      }
      
      // Step 2: Clear ALL cached data and notify backend
      await handleDisconnect();
      
      // Step 3: Wait for disconnect to complete
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Step 4: Request new connection (this opens Phantom popup)
      console.log('📱 Opening Phantom for new wallet selection...');
      const response = await phantomProvider.connect();
      
      if (response.publicKey) {
        const address = response.publicKey.toString();
        console.log('✅ Changed to wallet:', address);
        
        setWalletAddress(address);
        setIsConnected(true);
        
        localStorage.setItem('lastConnectedWallet', address);
        
        // CRITICAL: Sync new wallet with backend
        console.log('🔄 Syncing new wallet with backend...');
        const syncResult = await syncWithBackend(address);
        
        return { success: true, address, backendSynced: syncResult.success };
      }
      
    } catch (err) {
      console.error('❌ Change wallet error:', err);
      
      if (err.code === 4001) {
        setError('Wallet-Wechsel vom Benutzer abgebrochen');
      } else {
        setError(err.message || 'Wallet-Wechsel fehlgeschlagen');
      }
      
      return { success: false, error: err.message };
    } finally {
      setIsConnecting(false);
    }
  }, [handleDisconnect, syncWithBackend]);

  // Sign message (for verification)
  const signMessage = useCallback(async (message) => {
    if (!provider || !isConnected) {
      return { success: false, error: 'Wallet not connected' };
    }
    
    try {
      const encodedMessage = new TextEncoder().encode(message);
      const signedMessage = await provider.signMessage(encodedMessage, 'utf8');
      return { success: true, signature: signedMessage };
    } catch (err) {
      console.error('Sign message error:', err);
      return { success: false, error: err.message };
    }
  }, [provider, isConnected]);

  const contextValue = {
    // State
    walletAddress,
    isConnected,
    isConnecting,
    provider,
    error,
    backendSynced,
    tradingEngineReady,
    
    // Actions
    connectWallet,
    disconnectWallet,
    changeWallet,
    signMessage,
    syncWithBackend,
    autoStartTradingEngine,
    
    // Helpers
    shortAddress: walletAddress 
      ? `${walletAddress.slice(0, 4)}...${walletAddress.slice(-4)}`
      : null,
    
    // Check if Phantom is installed
    isPhantomInstalled: typeof window !== 'undefined' && window.solana?.isPhantom
  };

  return (
    <PhantomWalletContext.Provider value={contextValue}>
      {children}
    </PhantomWalletContext.Provider>
  );
};

export default PhantomWalletProvider;
