import React from 'react';
import { usePhantomWallet } from '../context/PhantomWalletContext';
import { Button } from './ui/button';
import { 
  Wallet, 
  RefreshCw, 
  ExternalLink, 
  Copy, 
  LogOut,
  SwitchCamera,
  AlertCircle,
  CheckCircle,
  Zap
} from 'lucide-react';
import { toast } from 'sonner';

const WalletConnect = ({ className = '' }) => {
  const {
    walletAddress,
    isConnected,
    isConnecting,
    error,
    connectWallet,
    disconnectWallet,
    changeWallet,
    shortAddress,
    isPhantomInstalled,
    backendSynced,
    tradingEngineReady
  } = usePhantomWallet();

  const [copied, setCopied] = React.useState(false);

  const handleConnect = async () => {
    const result = await connectWallet();
    if (result.success) {
      if (result.backendSynced) {
        toast.success('Wallet verbunden & synchronisiert', {
          description: `Trading Engine bereit - ${result.address.slice(0, 8)}...`
        });
      } else {
        toast.success('Wallet verbunden', {
          description: `${result.address.slice(0, 8)}...${result.address.slice(-8)}`
        });
      }
    } else if (result.error) {
      toast.error('Verbindung fehlgeschlagen', {
        description: result.error
      });
    }
  };

  const handleDisconnect = async () => {
    const result = await disconnectWallet();
    if (result.success) {
      toast.success('Wallet getrennt');
    }
  };

  const handleChange = async () => {
    toast.info('Wechsle Wallet...', { duration: 2000 });
    const result = await changeWallet();
    if (result.success) {
      if (result.backendSynced) {
        toast.success('Wallet gewechselt & synchronisiert', {
          description: `Trading Engine bereit - ${result.address.slice(0, 8)}...`
        });
      } else {
        toast.success('Wallet gewechselt', {
          description: `Neue Adresse: ${result.address.slice(0, 8)}...`
        });
      }
    } else if (result.error && result.error !== 'User rejected the request.') {
      toast.error('Wechsel fehlgeschlagen', {
        description: result.error
      });
    }
  };

  const copyAddress = () => {
    if (walletAddress) {
      navigator.clipboard.writeText(walletAddress);
      setCopied(true);
      toast.success('Adresse kopiert');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const openExplorer = () => {
    if (walletAddress) {
      window.open(`https://solscan.io/account/${walletAddress}`, '_blank');
    }
  };

  // Not connected state
  if (!isConnected) {
    return (
      <div className={`flex flex-col gap-2 ${className}`}>
        <Button
          onClick={handleConnect}
          disabled={isConnecting}
          className="bg-gradient-to-r from-purple-600 to-purple-800 hover:from-purple-700 hover:to-purple-900 text-white"
          data-testid="connect-wallet-btn"
        >
          {isConnecting ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Verbinde...
            </>
          ) : (
            <>
              <Wallet className="w-4 h-4 mr-2" />
              Wallet verbinden
            </>
          )}
        </Button>
        
        {!isPhantomInstalled && (
          <div className="flex items-center gap-2 text-xs text-yellow-500">
            <AlertCircle className="w-3 h-3" />
            <a 
              href="https://phantom.app/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="underline hover:text-yellow-400"
            >
              Phantom Wallet installieren
            </a>
          </div>
        )}
        
        {error && (
          <div className="text-xs text-red-400 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            {error}
          </div>
        )}
      </div>
    );
  }

  // Connected state
  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      {/* Wallet Address Display */}
      <div className="flex items-center justify-between bg-[#1E293B] rounded-lg px-3 py-2">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="font-mono text-sm text-white">{shortAddress}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={copyAddress}
            className="h-7 w-7 p-0 text-gray-400 hover:text-white"
            data-testid="copy-address-btn"
          >
            <Copy className={`w-3 h-3 ${copied ? 'text-green-500' : ''}`} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={openExplorer}
            className="h-7 w-7 p-0 text-gray-400 hover:text-white"
            data-testid="explorer-btn"
          >
            <ExternalLink className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Backend Sync Status */}
      <div className="flex items-center justify-between text-xs px-1">
        <div className="flex items-center gap-1">
          {backendSynced ? (
            <CheckCircle className="w-3 h-3 text-green-500" />
          ) : (
            <AlertCircle className="w-3 h-3 text-yellow-500" />
          )}
          <span className={backendSynced ? 'text-green-400' : 'text-yellow-400'}>
            Backend: {backendSynced ? 'Synchronisiert' : 'Nicht verbunden'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {tradingEngineReady ? (
            <Zap className="w-3 h-3 text-green-500" />
          ) : (
            <Zap className="w-3 h-3 text-gray-500" />
          )}
          <span className={tradingEngineReady ? 'text-green-400' : 'text-gray-400'}>
            Engine: {tradingEngineReady ? 'Aktiv' : 'Inaktiv'}
          </span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleChange}
          disabled={isConnecting}
          className="flex-1 border-purple-500/30 text-purple-400 hover:bg-purple-500/10"
          data-testid="change-wallet-btn"
        >
          {isConnecting ? (
            <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <SwitchCamera className="w-3 h-3 mr-1" />
          )}
          Wechseln
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleDisconnect}
          className="flex-1 border-red-500/30 text-red-400 hover:bg-red-500/10"
          data-testid="disconnect-wallet-btn"
        >
          <LogOut className="w-3 h-3 mr-1" />
          Trennen
        </Button>
      </div>
      
      {error && (
        <div className="text-xs text-red-400 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {error}
        </div>
      )}
    </div>
  );
};

export default WalletConnect;
