'use client';

import IntegrationsTab from '../../../components/groups/IntegrationsTab';

export default function WebhooksPage() {
  return (
    <div className="min-h-screen dark:bg-gray-900">
      <div className="max-w-7xl mx-auto p-3 sm:p-4 md:p-6">
        {/* Header */}
        <div className="mb-4 sm:mb-6 md:mb-8">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 dark:text-white">
            Webhook Integrations
          </h1>
          <p className="mt-1 sm:mt-2 text-xs sm:text-sm text-gray-600 dark:text-gray-400">
            Manage webhook integrations for Prometheus, Datadog, PagerDuty, Coralogix, and more
          </p>
        </div>

        {/* Info Banner */}
        <div className="mb-4 sm:mb-6 p-3 sm:p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <p className="text-xs sm:text-sm text-blue-800 dark:text-blue-200">
            Configure webhook endpoints to receive alerts from external monitoring tools and route them to your incident management workflow.
          </p>
        </div>

        {/* Integrations Content */}
        <IntegrationsTab />
      </div>
    </div>
  );
}
