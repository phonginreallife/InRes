'use client';

import Link from 'next/link';
import { BoltIcon, CubeIcon } from '@heroicons/react/24/outline';

const INTEGRATION_CATEGORIES = [
  {
    href: '/integrations/webhooks',
    title: 'Webhook Integrations',
    description: 'Connect external monitoring tools like Prometheus, Datadog, PagerDuty, Coralogix, and more',
    icon: BoltIcon,
    color: 'from-amber-500 to-orange-500',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    features: ['Prometheus AlertManager', 'Datadog', 'Grafana', 'PagerDuty', 'Coralogix', 'AWS CloudWatch', 'Generic Webhooks']
  },
  {
    href: '/agent-config',
    title: 'AI Plugins & Extensions',
    description: 'Manage AI agent plugins, MCP servers, and memory configurations',
    icon: CubeIcon,
    color: 'from-blue-500 to-indigo-500',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    features: ['Installed Plugins', 'Marketplace', 'MCP Servers', 'Allowed Tools', 'Local Memory', 'User Memory']
  }
];

export default function IntegrationsPage() {
  return (
    <div className="min-h-screen dark:bg-gray-900">
      <div className="max-w-7xl mx-auto p-3 sm:p-4 md:p-6">
        {/* Header */}
        <div className="mb-6 sm:mb-8 md:mb-10">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 dark:text-white">
            Integrations
          </h1>
          <p className="mt-1 sm:mt-2 text-xs sm:text-sm text-gray-600 dark:text-gray-400">
            Connect external tools and configure AI agent capabilities
          </p>
        </div>

        {/* Integration Categories */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
          {INTEGRATION_CATEGORIES.map((category) => (
            <Link
              key={category.href}
              href={category.href}
              className="group block p-5 sm:p-6 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-lg transition-all duration-200"
            >
              {/* Icon & Title */}
              <div className="flex items-start gap-4 mb-4">
                <div className={`p-3 rounded-xl bg-gradient-to-br ${category.color} shadow-lg`}>
                  <category.icon className="w-6 h-6 text-white" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                    {category.title}
                  </h2>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    {category.description}
                  </p>
                </div>
                <svg 
                  className="w-5 h-5 text-gray-400 group-hover:text-blue-500 group-hover:translate-x-1 transition-all" 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>

              {/* Features */}
              <div className={`p-3 rounded-lg ${category.bgColor}`}>
                <div className="flex flex-wrap gap-2">
                  {category.features.map((feature) => (
                    <span
                      key={feature}
                      className="px-2 py-1 text-xs font-medium text-gray-700 dark:text-gray-300 bg-white/80 dark:bg-gray-700/80 rounded-md"
                    >
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
