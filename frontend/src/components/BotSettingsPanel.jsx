import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
  Percent,
  Activity,
  RefreshCw
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Slider } from './ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { toast } from 'sonner';

const BotSettingsPanel = ({ settings: initialSettings, onClose, onSave }) => {
  const { t } = useTranslation();
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
    scan_interval_seconds: 3, // High frequency: 3 seconds
    smart_wallet_tracking: true,
    migration_detection: true,
    slippage_percent: 1.0,
    min_signal_score: 60,
    high_frequency_mode: true
  });
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('capital');

  useEffect(() => {
    if (initialSettings) {
      setSettings(prev => ({...prev, ...initialSettings}));
    }
  }, [initialSettings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await axios.put(`${API_URL}/bot/settings`, settings);
      toast.success(t('settings.settingsSaved'));
      onSave(response.data);
      onClose();
    } catch (error) {
      toast.error(t('settings.settingsFailed'));
    }
    setSaving(false);
  };

  const updateField = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const resetToDefaults = () => {
    setSettings({
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
      scan_interval_seconds: 3,
      smart_wallet_tracking: true,
      migration_detection: true,
      slippage_percent: 1.0,
      min_signal_score: 60,
      high_frequency_mode: true
    });
    toast.success(t('common.reset'));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" data-testid="bot-settings-panel">
      <div className="bg-[#0A0A0A] border border-[#1E293B] rounded-sm w-full max-w-2xl max-h-[90vh] overflow-hidden animate-in">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1E293B]">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-neon-violet" />
            <h2 className="font-heading font-bold text-lg">{t('settings.autoTradeSettings')}</h2>
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
              {t('settings.capitalManagement')}
            </TabsTrigger>
            <TabsTrigger value="trading" className="data-[state=active]:bg-[#1E293B]">
              <Target className="w-4 h-4 mr-2" />
              {t('settings.riskManagement')}
            </TabsTrigger>
            <TabsTrigger value="filters" className="data-[state=active]:bg-[#1E293B]">
              <Filter className="w-4 h-4 mr-2" />
              {t('settings.signalFilters')}
            </TabsTrigger>
            <TabsTrigger value="automation" className="data-[state=active]:bg-[#1E293B]">
              <Zap className="w-4 h-4 mr-2" />
              {t('settings.automation')}
            </TabsTrigger>
          </TabsList>

          <div className="p-4 overflow-y-auto max-h-[60vh]">
            {/* Capital Management */}
            <TabsContent value="capital" className="space-y-6 mt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-neon-green" />
                  {t('settings.capitalManagement')}
                </h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs">{t('settings.totalBudget')} (SOL)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0.1"
                      value={settings.total_budget_sol}
                      onChange={(e) => updateField('total_budget_sol', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                      data-testid="total-budget-input"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">{t('settings.minTradeSol')}</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={settings.min_trade_sol}
                      onChange={(e) => updateField('min_trade_sol', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                      data-testid="min-trade-input"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">{t('settings.tradeSize')}</Label>
                    <span className="font-mono text-neon-cyan">{settings.max_trade_percent}% {t('portfolio.ofBudget', { budget: '' }).replace('von  SOL Budget', '')}</span>
                  </div>
                  <Slider
                    value={[settings.max_trade_percent]}
                    onValueChange={(v) => updateField('max_trade_percent', v[0])}
                    min={5}
                    max={50}
                    step={5}
                    data-testid="trade-size-slider"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Max {(settings.total_budget_sol * settings.max_trade_percent / 100).toFixed(4)} SOL pro Trade
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">{t('settings.maxOpenTrades')}</Label>
                    <span className="font-mono">{settings.max_parallel_trades}</span>
                  </div>
                  <Slider
                    value={[settings.max_parallel_trades]}
                    onValueChange={(v) => updateField('max_parallel_trades', v[0])}
                    min={1}
                    max={10}
                    step={1}
                    data-testid="max-trades-slider"
                  />
                </div>
              </div>
            </TabsContent>

            {/* Risk Management */}
            <TabsContent value="trading" className="space-y-6 mt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Shield className="w-4 h-4 text-neon-cyan" />
                  {t('settings.riskManagement')}
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-xs">{t('settings.takeProfit')}</Label>
                      <span className="font-mono text-neon-green">+{settings.take_profit_percent}%</span>
                    </div>
                    <Slider
                      value={[settings.take_profit_percent]}
                      onValueChange={(v) => updateField('take_profit_percent', v[0])}
                      min={10}
                      max={500}
                      step={10}
                      data-testid="take-profit-slider"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-xs">{t('settings.stopLoss')}</Label>
                      <span className="font-mono text-neon-red">-{settings.stop_loss_percent}%</span>
                    </div>
                    <Slider
                      value={[settings.stop_loss_percent]}
                      onValueChange={(v) => updateField('stop_loss_percent', v[0])}
                      min={5}
                      max={50}
                      step={5}
                      data-testid="stop-loss-slider"
                    />
                  </div>
                </div>

                <div className="p-3 bg-[#0F172A] border border-[#1E293B] rounded-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <TrendingDown className="w-4 h-4 text-neon-yellow" />
                      <span className="text-sm">{t('settings.trailingStop')}</span>
                    </div>
                    <Switch
                      checked={settings.trailing_stop_enabled}
                      onCheckedChange={(v) => updateField('trailing_stop_enabled', v)}
                      data-testid="trailing-stop-switch"
                    />
                  </div>
                  {settings.trailing_stop_enabled && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-2">
                        <Label className="text-xs">{t('settings.trailingStopPercent')}</Label>
                        <span className="font-mono">{settings.trailing_stop_percent}%</span>
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
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-xs">{t('settings.dailyLossLimit')}</Label>
                      <span className="font-mono text-neon-red">{settings.max_daily_loss_percent}%</span>
                    </div>
                    <Slider
                      value={[settings.max_daily_loss_percent]}
                      onValueChange={(v) => updateField('max_daily_loss_percent', v[0])}
                      min={5}
                      max={100}
                      step={5}
                      data-testid="daily-loss-slider"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-xs">{t('settings.lossStreakLimit')}</Label>
                      <span className="font-mono">{settings.max_loss_streak} {t('settings.consecutiveLosses')}</span>
                    </div>
                    <Slider
                      value={[settings.max_loss_streak]}
                      onValueChange={(v) => updateField('max_loss_streak', v[0])}
                      min={1}
                      max={10}
                      step={1}
                      data-testid="loss-streak-slider"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">{t('settings.slippage')}</Label>
                    <span className="font-mono">{settings.slippage_percent}%</span>
                  </div>
                  <Slider
                    value={[settings.slippage_percent]}
                    onValueChange={(v) => updateField('slippage_percent', v[0])}
                    min={0.5}
                    max={5}
                    step={0.5}
                    data-testid="slippage-slider"
                  />
                </div>
              </div>
            </TabsContent>

            {/* Signal Filters */}
            <TabsContent value="filters" className="space-y-6 mt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Filter className="w-4 h-4 text-neon-violet" />
                  {t('settings.signalFilters')}
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs">{t('settings.minLiquidityUsd')}</Label>
                    <Input
                      type="number"
                      step="1000"
                      min="1000"
                      value={settings.min_liquidity_usd}
                      onChange={(e) => updateField('min_liquidity_usd', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                      data-testid="min-liquidity-input"
                    />
                    <p className="text-xs text-muted-foreground mt-1">Min. $10K empfohlen</p>
                  </div>
                  <div>
                    <Label className="text-xs">{t('settings.minVolumeUsd')}</Label>
                    <Input
                      type="number"
                      step="1000"
                      min="1000"
                      value={settings.min_volume_usd}
                      onChange={(e) => updateField('min_volume_usd', parseFloat(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                      data-testid="min-volume-input"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">{t('settings.minBuySellRatio')}</Label>
                    <span className="font-mono text-neon-green">{settings.min_buy_sell_ratio}x</span>
                  </div>
                  <Slider
                    value={[settings.min_buy_sell_ratio * 10]}
                    onValueChange={(v) => updateField('min_buy_sell_ratio', v[0] / 10)}
                    min={10}
                    max={30}
                    step={1}
                    data-testid="buy-sell-ratio-slider"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    {t('settings.buySellRatio')} &gt; 1.2 = starker Kaufdruck
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">{t('settings.maxDevWallet')}</Label>
                    <span className="font-mono">{settings.max_dev_wallet_percent}%</span>
                  </div>
                  <Slider
                    value={[settings.max_dev_wallet_percent]}
                    onValueChange={(v) => updateField('max_dev_wallet_percent', v[0])}
                    min={5}
                    max={30}
                    step={1}
                    data-testid="dev-wallet-slider"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs">{t('settings.minTokenAge')} ({t('time.minutes')})</Label>
                    <Input
                      type="number"
                      min="1"
                      value={settings.min_token_age_minutes}
                      onChange={(e) => updateField('min_token_age_minutes', parseInt(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">{t('settings.maxTokenAge')} ({t('time.hours')})</Label>
                    <Input
                      type="number"
                      min="1"
                      value={settings.max_token_age_hours}
                      onChange={(e) => updateField('max_token_age_hours', parseInt(e.target.value) || 0)}
                      className="bg-[#0F172A] border-[#1E293B] font-mono mt-1"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">{t('settings.minSignalScore')}</Label>
                    <span className="font-mono text-neon-cyan">{settings.min_signal_score}/100</span>
                  </div>
                  <Slider
                    value={[settings.min_signal_score]}
                    onValueChange={(v) => updateField('min_signal_score', v[0])}
                    min={30}
                    max={90}
                    step={5}
                    data-testid="signal-score-slider"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Höherer Score = weniger, aber qualitativ bessere Trades
                  </p>
                </div>
              </div>
            </TabsContent>

            {/* Automation */}
            <TabsContent value="automation" className="space-y-6 mt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Activity className="w-4 h-4 text-neon-green" />
                  {t('settings.highFrequencyMode')}
                </h3>

                <div className="p-3 bg-[#0F172A] border border-neon-cyan/30 rounded-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-neon-cyan" />
                      <span className="text-sm">{t('settings.highFrequencyMode')}</span>
                    </div>
                    <Switch
                      checked={settings.high_frequency_mode}
                      onCheckedChange={(v) => updateField('high_frequency_mode', v)}
                      data-testid="high-frequency-switch"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Scannt alle 2-3 Sekunden und verarbeitet mehrere Signale parallel
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">{t('settings.scanIntervalSeconds')}</Label>
                    <span className="font-mono">{settings.scan_interval_seconds}s</span>
                  </div>
                  <Slider
                    value={[settings.scan_interval_seconds]}
                    onValueChange={(v) => updateField('scan_interval_seconds', v[0])}
                    min={2}
                    max={30}
                    step={1}
                    data-testid="scan-interval-slider"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Empfohlen: 2-3 Sekunden für Hochfrequenz
                  </p>
                </div>

                <div className="p-3 bg-[#0F172A] border border-[#1E293B] rounded-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Target className="w-4 h-4 text-neon-violet" />
                      <span className="text-sm">{t('settings.smartWalletTracking')}</span>
                    </div>
                    <Switch
                      checked={settings.smart_wallet_tracking}
                      onCheckedChange={(v) => updateField('smart_wallet_tracking', v)}
                      data-testid="smart-wallet-switch"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Verfolgt profitable Wallets für bessere Signale
                  </p>
                </div>

                <div className="p-3 bg-[#0F172A] border border-[#1E293B] rounded-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <RefreshCw className="w-4 h-4 text-neon-yellow" />
                      <span className="text-sm">{t('settings.migrationDetection')}</span>
                    </div>
                    <Switch
                      checked={settings.migration_detection}
                      onCheckedChange={(v) => updateField('migration_detection', v)}
                      data-testid="migration-switch"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Erkennt Pump.fun → Raydium/Orca Migrationen
                  </p>
                </div>
              </div>
            </TabsContent>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-4 border-t border-[#1E293B]">
            <Button variant="outline" onClick={resetToDefaults} data-testid="reset-settings">
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('settings.resetDefaults')}
            </Button>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={onClose}>
                {t('common.cancel')}
              </Button>
              <Button 
                onClick={handleSave} 
                disabled={saving}
                className="bg-neon-green text-black hover:bg-neon-green/90"
                data-testid="save-settings"
              >
                <Save className="w-4 h-4 mr-2" />
                {saving ? t('common.loading') : t('settings.saveSettings')}
              </Button>
            </div>
          </div>
        </Tabs>
      </div>
    </div>
  );
};

export default BotSettingsPanel;
