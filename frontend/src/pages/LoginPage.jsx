import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Lock, Zap, AlertTriangle } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';

const LoginPage = () => {
  const { login } = useApp();
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isFirstTime, setIsFirstTime] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (pin.length < 4) {
      setError('PIN must be at least 4 digits');
      return;
    }
    
    setLoading(true);
    setError('');
    
    const result = await login(pin);
    
    if (!result.success) {
      setError(result.message);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" data-testid="login-page">
      <div className="w-full max-w-md">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-[#0A0A0A] border border-[#1E293B] mb-6">
            <Zap className="w-10 h-10 text-neon-cyan" />
          </div>
          <h1 className="text-4xl font-heading font-bold tracking-tight text-gradient-neon mb-2">
            PUMP TERMINAL
          </h1>
          <p className="text-muted-foreground font-body text-sm">
            Solana Token Trading Engine
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-[#0A0A0A] border border-[#1E293B] rounded-sm p-8">
          <div className="flex items-center gap-2 mb-6">
            <Lock className="w-5 h-5 text-neon-violet" />
            <h2 className="text-lg font-heading font-semibold">
              {isFirstTime === null ? 'Access Terminal' : isFirstTime ? 'Set Your PIN' : 'Enter PIN'}
            </h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted-foreground mb-2">
                Security PIN
              </label>
              <Input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                placeholder="Enter 4-6 digit PIN"
                maxLength={6}
                className="bg-[#0F172A] border-[#1E293B] focus:border-neon-cyan font-mono text-center text-2xl tracking-[0.5em]"
                data-testid="pin-input"
              />
              <p className="text-xs text-muted-foreground mt-2">
                First login will set your PIN
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-neon-red text-sm bg-neon-red/10 p-3 rounded-sm" data-testid="error-message">
                <AlertTriangle className="w-4 h-4" />
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading || pin.length < 4}
              className="w-full bg-neon-violet hover:bg-neon-violet/90 text-white font-semibold py-6"
              data-testid="login-button"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Authenticating...
                </span>
              ) : (
                'Access Terminal'
              )}
            </Button>
          </form>
        </div>

        {/* Footer */}
        <div className="text-center mt-6 text-xs text-muted-foreground">
          <p>Private Trading Terminal • Single User Mode</p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
