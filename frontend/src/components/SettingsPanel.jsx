import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { 
  X, 
  Settings, 
  Save,
  DollarSign,
  Target,
  AlertTriangle,
  Layers,
  Clock,
  Shield,
  Zap
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Slider } from './ui/slider';
import { toast } from 'sonner';

const SettingsPanel = ({ onClose }) => {
  const { settings, updateSettings } = useApp();
  
  const [localSettings, setLocalSettings] = useState({
    stake_per_trade: 0.1,
    max_loss_percent: 50,
    take_profit_percent: 100,
    stop_loss_percent: 30,
    max_parallel_trades: 3,
    max_daily_trades: 10,
    paper_mode: true,
    auto_mode: false
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings) {
      setLocalSettings(settings);
    }
  }, [settings]);

  const handleSave = async () => {
    setSaving(true);
    const result = await updateSettings(localSettings);
    if (result.success) {
      toast.success('Settings saved successfully');
      onClose();
    } else {
      toast.error('Failed to save settings');
    }
    setSaving(false);
  };

  const updateField = (field, value) => {
    setLocalSettings(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" data-testid="settings-panel">
      <div className="bg-[#0A0A0A] border border-[#1E293B] rounded-sm w-full max-w-lg max-h-[90vh] overflow-y-auto animate-in">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1E293B] sticky top-0 bg-[#0A0A0A] z-10">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-neon-violet" />
            <h2 className="font-heading font-bold text-lg">Trading Settings</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} data-testid="close-settings">
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Settings Form */}
        <div className="p-4 space-y-6">
          {/* Trade Amount */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-neon-cyan" />
              <Label className="text-sm font-semibold">Default Stake per Trade (SOL)</Label>
            </div>
            <Input
              type="number"
              step="0.01"
              min="0.01"
              value={localSettings.stake_per_trade}
              onChange={(e) => updateField('stake_per_trade', parseFloat(e.target.value) || 0)}
              className="bg-[#0F172A] border-[#1E293B] font-mono"
              data-testid="stake-input"
            />
            <div className="flex gap-2">
              {[0.05, 0.1, 0.25, 0.5, 1].map((amount) => (
                <Button
                  key={amount}
                  variant="outline"
                  size="sm"
                  className="flex-1 text-xs"
                  onClick={() => updateField('stake_per_trade', amount)}
                >
                  {amount}
                </Button>
              ))}
            </div>
          </div>

          {/* Take Profit */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-neon-green" />
                <Label className="text-sm font-semibold">Default Take Profit</Label>
              </div>
              <span className="font-mono text-neon-green">+{localSettings.take_profit_percent}%</span>
            </div>
            <Slider
              value={[localSettings.take_profit_percent]}
              onValueChange={(value) => updateField('take_profit_percent', value[0])}
              min={10}
              max={500}
              step={10}
              data-testid="take-profit-setting"
            />
          </div>

          {/* Stop Loss */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-neon-red" />
                <Label className="text-sm font-semibold">Default Stop Loss</Label>
              </div>
              <span className="font-mono text-neon-red">-{localSettings.stop_loss_percent}%</span>
            </div>
            <Slider
              value={[localSettings.stop_loss_percent]}
              onValueChange={(value) => updateField('stop_loss_percent', value[0])}
              min={5}
              max={80}
              step={5}
              data-testid="stop-loss-setting"
            />
          </div>

          {/* Max Loss */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-yellow-500" />
                <Label className="text-sm font-semibold">Max Daily Loss</Label>
              </div>
              <span className="font-mono text-yellow-500">-{localSettings.max_loss_percent}%</span>
            </div>
            <Slider
              value={[localSettings.max_loss_percent]}
              onValueChange={(value) => updateField('max_loss_percent', value[0])}
              min={10}
              max={100}
              step={10}
              data-testid="max-loss-setting"
            />
          </div>

          {/* Parallel Trades */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-neon-violet" />
                <Label className="text-sm font-semibold">Max Parallel Trades</Label>
              </div>
              <span className="font-mono">{localSettings.max_parallel_trades}</span>
            </div>
            <Slider
              value={[localSettings.max_parallel_trades]}
              onValueChange={(value) => updateField('max_parallel_trades', value[0])}
              min={1}
              max={10}
              step={1}
              data-testid="parallel-trades-setting"
            />
          </div>

          {/* Daily Trades */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-neon-cyan" />
                <Label className="text-sm font-semibold">Max Daily Trades</Label>
              </div>
              <span className="font-mono">{localSettings.max_daily_trades}</span>
            </div>
            <Slider
              value={[localSettings.max_daily_trades]}
              onValueChange={(value) => updateField('max_daily_trades', value[0])}
              min={1}
              max={50}
              step={1}
              data-testid="daily-trades-setting"
            />
          </div>

          {/* Toggles */}
          <div className="space-y-4 pt-4 border-t border-[#1E293B]">
            <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-neon-cyan" />
                <div>
                  <div className="font-semibold text-sm">Paper Trading Mode</div>
                  <div className="text-xs text-muted-foreground">Simulate trades without real funds</div>
                </div>
              </div>
              <Switch 
                checked={localSettings.paper_mode} 
                onCheckedChange={(checked) => updateField('paper_mode', checked)}
                data-testid="paper-mode-setting"
              />
            </div>

            <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-neon-green" />
                <div>
                  <div className="font-semibold text-sm">Auto Trading Mode</div>
                  <div className="text-xs text-muted-foreground">Execute trades automatically (use with caution)</div>
                </div>
              </div>
              <Switch 
                checked={localSettings.auto_mode} 
                onCheckedChange={(checked) => updateField('auto_mode', checked)}
                data-testid="auto-mode-setting"
              />
            </div>
          </div>

          {/* Warning */}
          {localSettings.auto_mode && (
            <div className="flex items-start gap-2 p-3 bg-neon-red/10 border border-neon-red/30 rounded-sm">
              <AlertTriangle className="w-4 h-4 text-neon-red mt-0.5" />
              <div className="text-sm">
                <span className="font-semibold text-neon-red">Warning:</span>{' '}
                <span className="text-muted-foreground">
                  Auto mode will execute trades without confirmation. Only enable if you fully understand the risks.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#1E293B] sticky bottom-0 bg-[#0A0A0A]">
          <Button
            className="w-full bg-neon-violet hover:bg-neon-violet/90"
            onClick={handleSave}
            disabled={saving}
            data-testid="save-settings"
          >
            {saving ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Saving...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Save className="w-4 h-4" />
                Save Settings
              </span>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SettingsPanel;
