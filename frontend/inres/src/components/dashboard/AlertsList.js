'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiClient } from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useOrg } from '../../contexts/OrgContext';

function getSeverityColor(severity) {
  switch (severity) {
    case 'critical': return 'text-red-600 bg-red-50 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800';
    case 'warning': return 'text-amber-600 bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800';
    case 'info': return 'text-blue-600 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800';
    default: return 'text-gray-600 bg-gray-50 border-gray-200 dark:bg-gray-700 dark:text-gray-400 dark:border-gray-600';
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'firing': return 'text-red-600 dark:text-red-400';
    case 'resolved': return 'text-primary-600 dark:text-primary-400';
    case 'acked': return 'text-amber-600 dark:text-amber-400';
    default: return 'text-gray-600 dark:text-gray-400';
  }
}

function formatTime(timeString) {
  if (!timeString) return '—';
  const date = new Date(timeString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
  return `${Math.floor(diffMins / 1440)}d ago`;
}

export default function AlertsList({ limit = 5 }) {
  const { session } = useAuth();
  const { currentOrg, currentProject } = useOrg();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAlerts = async () => {
      if (!session?.access_token || !currentOrg?.id) {
        setAlerts([]);
        setLoading(false);
        return;
      }

      try {
        apiClient.setToken(session.access_token);
        const data = await apiClient.getRecentAlerts(limit, {
          org_id: currentOrg.id,
          ...(currentProject?.id && { project_id: currentProject.id })
        });
        const alertsList = Array.isArray(data) ? data : (data?.alerts || []);
        setAlerts(alertsList);
        setError(null);
      } catch (err) {
        console.error('[AlertsList] Error:', err);
        setError(err.message);
        setAlerts([]);
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
  }, [session?.access_token, currentOrg?.id, currentProject?.id, limit]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-3 rounded-lg bg-gray-50 dark:bg-navy-700/30 animate-pulse">
            <div className="h-4 bg-gray-200 dark:bg-navy-600 rounded w-3/4 mb-2"></div>
            <div className="h-3 bg-gray-200 dark:bg-navy-600 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">Unable to load alerts</p>
      </div>
    );
  }

  if (!alerts.length) {
    return (
      <div className="text-center py-6">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-green-100 dark:bg-green-900/20 mb-2">
          <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-900 dark:text-white">All clear</p>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">No active alerts</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {alerts.map((alert) => (
        <Link 
          key={alert.id}
          href={`/alerts/${alert.id}`}
          className="block p-3 rounded-xl border border-gray-100 dark:border-navy-600/50 bg-white dark:bg-navy-700/30 hover:shadow-sm hover:-translate-y-0.5 transition-all"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full border ${getSeverityColor(alert.severity)}`}>
                  {alert.severity}
                </span>
                <span className={`text-xs font-medium ${getStatusColor(alert.status)}`}>
                  {alert.status}
                </span>
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {alert.title}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {alert.source || 'Unknown'} • {formatTime(alert.created_at)}
              </p>
            </div>
            <svg className="w-4 h-4 text-gray-300 dark:text-gray-600 flex-shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </Link>
      ))}
    </div>
  );
}
