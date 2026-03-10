import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Wallet, Send, ExternalLink, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function WithdrawModal({ isOpen, onClose }) {
  const [withdrawStatus, setWithdrawStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    target_wallet: '',
    amount_sol: '',
    pin: '',
    wallet_id: 0
  });
  const [txResult, setTxResult] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchWithdrawStatus();
    }
  }, [isOpen]);

  const fetchWithdrawStatus = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_URL}/api/withdraw/status`);
      setWithdrawStatus(response.data);
    } catch (error) {
      console.error('Error fetching withdraw status:', error);
      toast.error('Fehler beim Laden der Auszahlungsdaten');
    } finally {
      setLoading(false);
    }
  };

  const handleWithdraw = async () => {
    if (!formData.target_wallet) {
      toast.error('Bitte Ziel-Wallet eingeben');
      return;
    }
    if (!formData.pin) {
      toast.error('Bitte PIN eingeben');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        target_wallet: formData.target_wallet,
        pin: formData.pin,
        wallet_id: parseInt(formData.wallet_id) || 0
      };

      if (formData.amount_sol) {
        payload.amount_sol = parseFloat(formData.amount_sol);
      }

      const response = await axios.post(`${API_URL}/api/withdraw`, payload);
      
      if (response.data.success) {
        setTxResult(response.data);
        toast.success(`${response.data.amount_sol.toFixed(6)} SOL erfolgreich ausgezahlt!`);
        fetchWithdrawStatus();
      } else {
        toast.error(response.data.message || 'Auszahlung fehlgeschlagen');
      }
    } catch (error) {
      console.error('Withdraw error:', error);
      const errorMsg = error.response?.data?.detail || 'Auszahlung fehlgeschlagen';
      toast.error(errorMsg);
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setFormData({
      target_wallet: '',
      amount_sol: '',
      pin: '',
      wallet_id: 0
    });
    setTxResult(null);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) { onClose(); resetForm(); } }}>
      <DialogContent className="bg-[#0A0F1C] border-[#1E293B] text-white max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Wallet className="w-5 h-5 text-neon-green" />
            Gewinn auszahlen
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Überweise deinen Gewinn auf eine externe Wallet
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-neon-green" />
          </div>
        ) : txResult ? (
          // Erfolgsanzeige
          <div className="space-y-4 py-4">
            <div className="flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-neon-green/20 flex items-center justify-center">
                <CheckCircle className="w-10 h-10 text-neon-green" />
              </div>
            </div>
            <div className="text-center">
              <h3 className="text-2xl font-bold text-neon-green">
                {txResult.amount_sol.toFixed(6)} SOL
              </h3>
              <p className="text-gray-400 mt-1">erfolgreich ausgezahlt</p>
            </div>
            <div className="bg-[#1E293B] rounded-lg p-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">An:</span>
                <span className="font-mono text-xs">{txResult.to_wallet.slice(0, 12)}...{txResult.to_wallet.slice(-8)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">TX:</span>
                <a 
                  href={txResult.explorer_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-neon-green hover:underline flex items-center gap-1"
                >
                  {txResult.tx_signature.slice(0, 12)}...
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
            <Button 
              onClick={resetForm}
              className="w-full bg-[#1E293B] hover:bg-[#2D3A4F]"
            >
              Weitere Auszahlung
            </Button>
          </div>
        ) : (
          // Formular
          <div className="space-y-4 py-4">
            {/* Status-Übersicht */}
            {withdrawStatus && (
              <div className="bg-[#1E293B] rounded-lg p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-400">Realisierter P&L:</span>
                  <span className={`font-bold ${withdrawStatus.realized_pnl >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                    {withdrawStatus.realized_pnl >= 0 ? '+' : ''}{withdrawStatus.realized_pnl?.toFixed(6)} SOL
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Gesamtguthaben:</span>
                  <span>{withdrawStatus.total_balance_sol?.toFixed(6)} SOL</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">In Trades:</span>
                  <span>{withdrawStatus.capital_in_trades?.toFixed(6)} SOL</span>
                </div>
                <div className="border-t border-[#2D3A4F] pt-2 mt-2 flex justify-between">
                  <span className="text-gray-400">Max. auszahlbar:</span>
                  <span className="font-bold text-neon-green">{withdrawStatus.max_withdrawable?.toFixed(6)} SOL</span>
                </div>
              </div>
            )}

            {/* Wallet-Auswahl */}
            {withdrawStatus?.wallets?.length > 1 && (
              <div className="space-y-2">
                <Label>Von Wallet</Label>
                <select
                  value={formData.wallet_id}
                  onChange={(e) => setFormData({ ...formData, wallet_id: e.target.value })}
                  className="w-full bg-[#1E293B] border border-[#2D3A4F] rounded-lg px-3 py-2 text-white"
                >
                  {withdrawStatus.wallets.map((w) => (
                    <option key={w.wallet_id} value={w.wallet_id}>
                      Wallet {w.wallet_id}: {w.balance_sol.toFixed(4)} SOL ({w.public_key.slice(0, 8)}...)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Ziel-Wallet */}
            <div className="space-y-2">
              <Label>Ziel-Wallet (Solana-Adresse)</Label>
              <Input
                value={formData.target_wallet}
                onChange={(e) => setFormData({ ...formData, target_wallet: e.target.value })}
                placeholder="z.B. 9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
                className="bg-[#1E293B] border-[#2D3A4F]"
              />
            </div>

            {/* Betrag */}
            <div className="space-y-2">
              <Label>Betrag (SOL) - leer = gesamter Gewinn</Label>
              <Input
                type="number"
                step="0.001"
                min="0"
                value={formData.amount_sol}
                onChange={(e) => setFormData({ ...formData, amount_sol: e.target.value })}
                placeholder={`Max: ${withdrawStatus?.max_withdrawable?.toFixed(6) || '0'} SOL`}
                className="bg-[#1E293B] border-[#2D3A4F]"
              />
            </div>

            {/* PIN */}
            <div className="space-y-2">
              <Label>Sicherheits-PIN</Label>
              <Input
                type="password"
                value={formData.pin}
                onChange={(e) => setFormData({ ...formData, pin: e.target.value })}
                placeholder="PIN eingeben"
                className="bg-[#1E293B] border-[#2D3A4F]"
                maxLength={10}
              />
            </div>

            {/* Warnung */}
            <div className="flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
              <AlertCircle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-yellow-200">
                Überprüfen Sie die Ziel-Adresse sorgfältig. Transaktionen auf der Blockchain sind nicht rückgängig zu machen!
              </p>
            </div>
          </div>
        )}

        {!txResult && !loading && (
          <DialogFooter>
            <Button
              variant="outline"
              onClick={onClose}
              className="border-[#2D3A4F]"
            >
              Abbrechen
            </Button>
            <Button
              onClick={handleWithdraw}
              disabled={submitting || !formData.target_wallet || !formData.pin}
              className="bg-neon-green hover:bg-neon-green/80 text-black"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Sende...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Auszahlen
                </>
              )}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
