'use client';

import { useState } from 'react';
import { apiClient } from '../../lib/api';
import { useOrg } from '../../contexts/OrgContext';
import toast from 'react-hot-toast';

const PROVIDER_TYPES = [
  {
    id: 'uptimerobot',
    name: 'UptimeRobot',
    icon: '🤖',
    description: 'Free uptime monitoring with 50 monitors',
    apiKeyHelp: 'Get your API key from UptimeRobot Dashboard → My Settings → API Settings → Main API Key',
    apiKeyUrl: 'https://uptimerobot.com/dashboard#mySettings',
  },
  {
    id: 'checkly',
    name: 'Checkly',
    icon: '🦎',
    description: 'API & browser monitoring with Playwright',
    apiKeyHelp: 'Enter API key and Account ID in format: YOUR_API_KEY:YOUR_ACCOUNT_ID',
    apiKeyUrl: 'https://app.checklyhq.com/settings/user/api-keys',
    apiKeyPlaceholder: 'api_key:account_id',
    requiresAccountId: true,
  },
  {
    id: 'pingdom',
    name: 'Pingdom',
    icon: '📍',
    description: 'Transaction & RUM monitoring',
    apiKeyHelp: 'Get your API key from Pingdom Settings',
    comingSoon: true,
  },
  {
    id: 'betterstack',
    name: 'Better Stack',
    icon: '🟢',
    description: 'Uptime monitoring & status pages',
    apiKeyHelp: 'Get your API key from Better Stack Dashboard',
    comingSoon: true,
  },
];

export default function UptimeProviderModal({ isOpen, onClose, onSuccess }) {
  const { currentOrg } = useOrg();
  const [step, setStep] = useState(1);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    api_key: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleProviderSelect = (provider) => {
    if (provider.comingSoon) {
      toast.error(`${provider.name} integration coming soon!`);
      return;
    }
    setSelectedProvider(provider);
    setFormData({ ...formData, name: `My ${provider.name}` });
    setStep(2);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await apiClient.createUptimeProvider({
        name: formData.name,
        provider_type: selectedProvider.id,
        api_key: formData.api_key,
        organization_id: currentOrg?.id,
      });

      toast.success(`${selectedProvider.name} connected successfully! Syncing monitors...`);
      onSuccess?.();
      onClose();
    } catch (err) {
      console.error('Failed to create provider:', err);
      setError(err.message || 'Failed to connect provider');
      toast.error(err.message || 'Failed to connect provider');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setStep(1);
    setSelectedProvider(null);
    setError(null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {step === 2 && (
              <button
                onClick={handleBack}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            )}
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {step === 1 ? 'Connect Uptime Provider' : `Connect ${selectedProvider?.name}`}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {step === 1 ? (
            /* Step 1: Provider Selection */
            <div className="space-y-3">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Import monitors from your existing uptime monitoring service
              </p>
              
              <div className="grid grid-cols-2 gap-3">
                {PROVIDER_TYPES.map((provider) => (
                  <button
                    key={provider.id}
                    onClick={() => handleProviderSelect(provider)}
                    disabled={provider.comingSoon}
                    className={`p-4 rounded-xl border-2 text-left transition-all ${
                      provider.comingSoon
                        ? 'border-gray-200 dark:border-gray-700 opacity-50 cursor-not-allowed'
                        : 'border-gray-200 dark:border-gray-700 hover:border-primary-500 dark:hover:border-primary-500 hover:shadow-md'
                    }`}
                  >
                    <div className="text-2xl mb-2">{provider.icon}</div>
                    <div className="font-semibold text-gray-900 dark:text-white text-sm">
                      {provider.name}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {provider.description}
                    </div>
                    {provider.comingSoon && (
                      <span className="inline-block mt-2 text-[10px] font-medium px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-full">
                        Coming Soon
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Step 2: API Key Input */
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <span className="text-2xl">{selectedProvider?.icon}</span>
                <div>
                  <div className="font-medium text-gray-900 dark:text-white">
                    {selectedProvider?.name}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {selectedProvider?.description}
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Display Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Production Monitors"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {selectedProvider?.requiresAccountId ? 'API Key : Account ID' : 'API Key'}
                </label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                  placeholder={selectedProvider?.apiKeyPlaceholder || "Enter your API key"}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent font-mono text-sm"
                  required
                />
                <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                  {selectedProvider?.apiKeyHelp}
                </p>
                {selectedProvider?.apiKeyUrl && (
                  <a
                    href={selectedProvider.apiKeyUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 mt-1 text-xs text-primary-600 dark:text-primary-400 hover:underline"
                  >
                    {selectedProvider?.requiresAccountId ? 'Get API Key & Account ID' : 'Get API Key'}
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                )}
                {selectedProvider?.requiresAccountId && (
                  <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg text-xs text-blue-700 dark:text-blue-400">
                    <strong>Format:</strong> Combine your API key and Account ID with a colon separator.
                    <br />
                    <strong>Example:</strong> <code className="bg-blue-100 dark:bg-blue-800 px-1 rounded">cu_abc123xyz:12345678-abcd-1234-5678-abcdef123456</code>
                  </div>
                )}
              </div>

              {error && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
                  {error}
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleBack}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Connecting...' : 'Connect'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
