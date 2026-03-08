import React, { useState, useEffect } from 'react';
import axios from 'axios';
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
  Zap,
  Bot,
  TrendingUp,
  TrendingDown,
  Filter,
  Percent
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Slider } from './ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { toast } from 'sonner';

const BotSettingsPanel = ({ settings: initialSettings, onClose, onSave }) => {
  const { API_URL } = useApp();
  
  const [settings, setSettings] = useState({
    total_budget_sol: 0.5,
    max_trade_percent: 20,
    min_trade_sol: 0.01,
    max_parallel_trades: 5,
    take_profit_percent: 100,
    stop_loss_percent: 25,
    trailing_stop_enabled: false,
    trailing_stop_percent: 10,
    max_daily_loss_percent: 50,
    max_loss_streak: 3,
    min_liquidity_usd: 5000,
    max_dev_wallet_percent: 15,
    max_top10_wallet_percent: 50,
    min_token_age_minutes: 5,
    max_token_age_hours: 24,
    min_buy_sell_ratio: 1.2,
    min_volume_usd: 1000,
    auto_trade_enabled: false,
    paper_mode: true,
    scan_interval_seconds: 30,
    smart_wallet_tracking: true,
    migration_detection: true
  });
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('capital');

  useEffect(() => {
    if (initialSettings) {
      setSettings(initialSettings);
    }
  }, [initialSettings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await axios.put(`${API_URL}/bot/settings`, settings);
      toast.success('Settings saved successfully');
      onSave(response.data);
      onClose();
    } catch (error) {
      toast.error('Failed to save settings');
    }
    setSaving(false);
  };

  const updateField = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" data-testid="bot-settings-panel">
      <div className="bg-[#0A0A0A] border border-[#1E293B] rounded-sm w-full max-w-2xl max-h-[90vh] overflow-hidden animate-in">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1E293B]">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-neon-violet" />
            <h2 className="font-heading font-bold text-lg">Trading Bot Settings</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} data-testid="close-settings">
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full">
          <TabsList className="w-full justify-start px-4 pt-2 bg-transparent border-b border-[#1E293B] rounded-none">
            <TabsTrigger value="capital" className="data-[state=active]:bg-[#1E293B]">
              <DollarSign className="w-4 h-4 mr-2" />
              Capital
            </TabsTrigger>
            <TabsTrigger value="trading" className="data-[state=active]:bg-[#1E293B]">
              <Target className="w-4 h-4 mr-2" />
              Trading
            </TabsTrigger>
            <TabsTrigger value="filters" className="data-[state=active]:bg-[#1E293B]">
              <Filter className="w-4 h-4 mr-2" />
              Filters
            </TabsTrigger>
            <TabsTrigger value="automation" className="data-[state=active]:bg-[#1E293B]">
              <Zap className="w-4 h-4 mr-2" />
              Automation
            </TabsTrigger>
          </TabsList>

          <div className="p-4 overflow-y-auto max-h-[60vh]">
            {/* Capital Management */}
            <TabsContent value="capital" className="space-y-6 mt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-neon-green" />
                  Budget Configuration
                </h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs">Total Budget (SOL)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0.1"
                      value={settings.total_budget_sol}
                      onChange={(e) => updateField('total_budget_sol', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Min Trade Amount (SOL)</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={settings.min_trade_sol}
                      onChange={(e) => updateField('min_trade_sol', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Max Trade Size</Label>
                    <span className="font-mono text-neon-cyan">{settings.max_trade_percent}% of budget</span>
                  </div>
                  <Slider
                    value={[settings.max_trade_percent]}
                    onValueChange={(v) => updateField('max_trade_percent', v[0])}
                    min={5}
                    max={50}
                    step={5}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Max {(settings.total_budget_sol * settings.max_trade_percent / 100).toFixed(4)} SOL per trade
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Max Parallel Trades</Label>
                    <span className="font-mono">{settings.max_parallel_trades}</span>
                  </div>
                  <Slider
                    value={[settings.max_parallel_trades]}
                    onValueChange={(v) => updateField('max_parallel_trades', v[0])}
                    min={1}
                    max={10}
                    step={1}
                  />
                </div>
              </div>
            </TabsContent>

            {/* Trading Parameters */}
            <TabsContent value="trading" className="space-y-6 mt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-neon-green" />
                  Take Profit / Stop Loss
                </h3>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Take Profit</Label>
                    <span className="font-mono text-neon-green">+{settings.take_profit_percent}%</span>
                  </div>
                  <Slider
                    value={[settings.take_profit_percent]}
                    onValueChange={(v) => updateField('take_profit_percent', v[0])}
                    min={20}
                    max={500}
                    step={10}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Stop Loss</Label>
                    <span className="font-mono text-neon-red">-{settings.stop_loss_percent}%</span>
                  </div>
                  <Slider
                    value={[settings.stop_loss_percent]}
                    onValueChange={(v) => updateField('stop_loss_percent', v[0])}
                    min={5}
                    max={50}
                    step={5}
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
                  <div>
                    <div className="font-semibold text-sm">Trailing Stop</div>
                    <div className="text-xs text-muted-foreground">Lock in profits as price rises</div>
                  </div>
                  <Switch 
                    checked={settings.trailing_stop_enabled} 
                    onCheckedChange={(v) => updateField('trailing_stop_enabled', v)}
                  />
                </div>

                {settings.trailing_stop_enabled && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-xs">Trailing Stop Distance</Label>
                      <span className="font-mono text-yellow-500">{settings.trailing_stop_percent}%</span>
                    </div>
                    <Slider
                      value={[settings.trailing_stop_percent]}
                      onValueChange={(v) => updateField('trailing_stop_percent', v[0])}
                      min={5}
                      max={30}
                      step={1}
                    />
                  </div>
                )}

                <h3 className="text-sm font-semibold flex items-center gap-2 pt-4">
                  <Shield className="w-4 h-4 text-neon-red" />
                  Risk Management
                </h3>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Max Daily Loss</Label>
                    <span className="font-mono text-neon-red">-{settings.max_daily_loss_percent}%</span>
                  </div>
                  <Slider
                    value={[settings.max_daily_loss_percent]}
                    onValueChange={(v) => updateField('max_daily_loss_percent', v[0])}
                    min={10}
                    max={100}
                    step={10}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Pause After Consecutive Losses</Label>
                    <span className="font-mono">{settings.max_loss_streak} trades</span>
                  </div>
                  <Slider
                    value={[settings.max_loss_streak]}
                    onValueChange={(v) => updateField('max_loss_streak', v[0])}
                    min={2}
                    max={10}
                    step={1}
                  />
                </div>
              </div>
            </TabsContent>

            {/* Token Filters */}
            <TabsContent value="filters" className="space-y-6 mt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Filter className="w-4 h-4 text-neon-cyan" />
                  Token Requirements
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs">Min Liquidity (USD)</Label>
                    <Input
                      type="number"
                      value={settings.min_liquidity_usd}
                      onChange={(e) => updateField('min_liquidity_usd', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Min Volume 24h (USD)</Label>
                    <Input
                      type="number"
                      value={settings.min_volume_usd}
                      onChange={(e) => updateField('min_volume_usd', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Max Dev Wallet Holdings</Label>
                    <span className="font-mono text-neon-red">{settings.max_dev_wallet_percent}%</span>
                  </div>
                  <Slider
                    value={[settings.max_dev_wallet_percent]}
                    onValueChange={(v) => updateField('max_dev_wallet_percent', v[0])}
                    min={5}
                    max={30}
                    step={1}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Max Top 10 Wallets Holdings</Label>
                    <span className="font-mono text-yellow-500">{settings.max_top10_wallet_percent}%</span>
                  </div>
                  <Slider
                    value={[settings.max_top10_wallet_percent]}
                    onValueChange={(v) => updateField('max_top10_wallet_percent', v[0])}
                    min={20}
                    max={80}
                    step={5}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Min Buy/Sell Ratio</Label>
                    <span className="font-mono text-neon-green">{settings.min_buy_sell_ratio}x</span>
                  </div>
                  <Slider
                    value={[settings.min_buy_sell_ratio * 10]}
                    onValueChange={(v) => updateField('min_buy_sell_ratio', v[0] / 10)}
                    min={10}
                    max={30}
                    step={1}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs">Min Token Age (minutes)</Label>
                    <Input
                      type="number"
                      value={settings.min_token_age_minutes}
                      onChange={(e) => updateField('min_token_age_minutes', parseInt(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Max Token Age (hours)</Label>
                    <Input
                      type="number"
                      value={settings.max_token_age_hours}
                      onChange={(e) => updateField('max_token_age_hours', parseInt(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Automation */}
            <TabsContent value="automation" className="space-y-6 mt-0">
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gradient-to-r from-neon-violet/10 to-neon-cyan/10 rounded-sm border border-neon-violet/30">
                  <div>
                    <div className="font-semibold flex items-center gap-2">
                      <Zap className="w-4 h-4 text-neon-green" />
                      Auto Trading
                    </div>
                    <div className="text-xs text-muted-foreground">Execute trades automatically based on signals</div>
                  </div>
                  <Switch 
                    checked={settings.auto_trade_enabled} 
                    onCheckedChange={(v) => updateField('auto_trade_enabled', v)}
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
                  <div>
                    <div className="font-semibold text-sm flex items-center gap-2">
                      <Shield className="w-4 h-4 text-neon-cyan" />
                      Paper Trading Mode
                    </div>
                    <div className="text-xs text-muted-foreground">Simulate trades without real funds</div>
                  </div>
                  <Switch 
                    checked={settings.paper_mode} 
                    onCheckedChange={(v) => updateField('paper_mode', v)}
                  />
                </div>

                {!settings.paper_mode && (
                  <div className="p-3 bg-neon-red/10 border border-neon-red/30 rounded-sm">
                    <div className="flex items-center gap-2 text-neon-red">
                      <AlertTriangle className="w-4 h-4" />
                      <span className="font-semibold text-sm">Live Trading Warning</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Real funds will be used. Make sure you understand the risks.
                    </p>
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Scan Interval</Label>
                    <span className="font-mono">{settings.scan_interval_seconds}s</span>
                  </div>
                  <Slider
                    value={[settings.scan_interval_seconds]}
                    onValueChange={(v) => updateField('scan_interval_seconds', v[0])}
                    min={10}
                    max={120}
                    step={10}
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
                  <div>
                    <div className="font-semibold text-sm">Smart Wallet Tracking</div>
                    <div className="text-xs text-muted-foreground">Track profitable wallets for signals</div>
                  </div>
                  <Switch 
                    checked={settings.smart_wallet_tracking} 
                    onCheckedChange={(v) => updateField('smart_wallet_tracking', v)}
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-[#050505] rounded-sm border border-[#1E293B]">
                  <div>
                    <div className="font-semibold text-sm">Migration Detection</div>
                    <div className="text-xs text-muted-foreground">Detect tokens migrating to larger DEXes</div>
                  </div>
                  <Switch 
                    checked={settings.migration_detection} 
                    onCheckedChange={(v) => updateField('migration_detection', v)}
                  />
                </div>
              </div>
            </TabsContent>
          </div>
        </Tabs>

        {/* Footer */}
        <div className="p-4 border-t border-[#1E293B]">
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

export default BotSettingsPanel;
