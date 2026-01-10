'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '../../../contexts/AuthContext';
import { apiClient } from '../../../lib/api';
import { MarkdownRenderer } from '../../../components/ui';

// Toast notification component
function Toast({ message, type, onClose }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const bgColor = type === 'success' 
    ? 'bg-primary-500' 
    : type === 'error' 
    ? 'bg-red-500' 
    : 'bg-gray-700';

  return (
    <div className={`fixed bottom-4 right-4 ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg z-50 animate-slide-up flex items-center gap-2`}>
      {type === 'success' && (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      )}
      {type === 'error' && (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      )}
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
}

// Copy button component
function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="group inline-flex items-center gap-1.5 text-sm text-gray-900 dark:text-white font-mono hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
      title={`Copy ${label}`}
    >
      <span className="truncate max-w-[200px]">{text}</span>
      <span className={`transition-all duration-200 ${copied ? 'text-green-500' : 'text-gray-400 opacity-0 group-hover:opacity-100'}`}>
        {copied ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        )}
      </span>
    </button>
  );
}

export default function IncidentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { session } = useAuth();
  const [incident, setIncident] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null); // Track which action is loading
  const [toast, setToast] = useState(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const fetchIncident = async () => {
      if (!session?.access_token || !params.id) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        apiClient.setToken(session.access_token);
        const data = await apiClient.getIncident(params.id);
        setIncident(data);
        setEvents(data.recent_events || []);
        setError(null);
      } catch (err) {
        console.error('Error fetching incident:', err);
        setError('Failed to fetch incident details');
      } finally {
        setLoading(false);
      }
    };

    fetchIncident();
  }, [session, params.id]);

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
  }, []);

  const handleAction = async (action) => {
    if (!incident) return;

    try {
      setActionLoading(action);

      switch (action) {
        case 'acknowledge':
          await apiClient.acknowledgeIncident(incident.id);
          showToast('Incident acknowledged successfully');
          break;
        case 'resolve':
          await apiClient.resolveIncident(incident.id);
          showToast('Incident resolved successfully');
          break;
        case 'escalate':
          await apiClient.escalateIncident(incident.id);
          showToast('Incident escalated successfully');
          break;
      }

      // Refresh incident data
      const data = await apiClient.getIncident(params.id);
      setIncident(data);
      setEvents(data.recent_events || []);

    } catch (err) {
      console.error(`Error ${action} incident:`, err);
      const errorMessage = err.response?.data?.details || err.response?.data?.error || err.message || `Failed to ${action} incident`;
      showToast(errorMessage, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'triggered':
        return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
      case 'acknowledged':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
      case 'resolved':
        return 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400';
      default:
        return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400';
    }
  };

  const getUrgencyColor = (urgency) => {
    return urgency === 'high'
      ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
      : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  };

  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
        return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
      case 'high':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
      case 'medium':
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';
      case 'low':
        return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
      default:
        return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
    }
  };

  const getTimelineEventColor = (eventType) => {
    switch (eventType) {
      case 'triggered':
        return 'bg-red-500';
      case 'acknowledged':
        return 'bg-amber-500';
      case 'resolved':
        return 'bg-primary-500';
      case 'escalated':
        return 'bg-red-400';
      default:
        return 'bg-gray-400';
    }
  };

  const formatTimeSince = (dateString) => {
    const now = new Date();
    const date = new Date(dateString);
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-4 border-gray-200 dark:border-gray-700"></div>
          <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-4 border-primary-500 border-t-transparent animate-spin"></div>
        </div>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 animate-fade-in">
        <div className="flex">
          <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="ml-3">
            <p className="text-sm text-red-700 dark:text-red-300">{error || 'Incident not found'}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-6 transition-all duration-500 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
      {/* Toast Notification */}
      {toast && (
        <Toast 
          message={toast.message} 
          type={toast.type} 
          onClose={() => setToast(null)} 
        />
      )}

      {/* Header Card */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Back + Title Row */}
            <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => router.back()}
                className="p-2 -ml-2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-all duration-200"
                title="Go back"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </button>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  {incident.status === 'triggered' && (
                    <span className="relative flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                    </span>
                  )}
              Incident #{incident.id.slice(-8)}
            </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  {incident.title}
                </p>
              </div>
          </div>

            {/* Status Badges */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Status Badge */}
              <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 ${getStatusColor(incident.status)}`}>
                {incident.status === 'triggered' && (
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                )}
                {incident.status === 'acknowledged' && (
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                  </svg>
                )}
                {incident.status === 'resolved' && (
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                )}
              {incident.status.toUpperCase()}
            </span>

              {/* Urgency Badge */}
              <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg ${getUrgencyColor(incident.urgency)}`}>
                {incident.urgency === 'high' && (
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z" clipRule="evenodd" />
                  </svg>
                )}
                {incident.urgency === 'high' ? 'HIGH URGENCY' : 'NORMAL'}
            </span>

              {/* Severity Badge */}
            {incident.severity && (
                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg ${getSeverityColor(incident.severity)}`}>
                  {(incident.severity?.toLowerCase() === 'critical' || incident.severity?.toLowerCase() === 'error') && (
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  )}
                {incident.severity.toUpperCase()}
              </span>
            )}

              {/* Time since created */}
              <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
                Created {formatTimeSince(incident.created_at)}
              </span>
            </div>
        </div>

        {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-2 flex-shrink-0">
            {/* Ask AI Agent Button */}
            <button
              onClick={() => router.push(`/ai-agent?incident=${incident.id}`)}
              className="ask-ai-btn group relative inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 bg-gradient-to-r from-violet-100 via-purple-50 to-indigo-100 hover:from-violet-200 hover:via-purple-100 hover:to-indigo-200 border border-violet-300/60 text-violet-700 hover:text-violet-900 focus:outline-none focus:ring-2 focus:ring-violet-400 focus:ring-offset-2 dark:from-violet-900/30 dark:via-purple-900/20 dark:to-indigo-900/30 dark:hover:from-violet-800/40 dark:hover:via-purple-800/30 dark:hover:to-indigo-800/40 dark:border-violet-600/40 dark:text-violet-300 dark:hover:text-violet-200 overflow-hidden"
            >
              {/* Continuous shimmer overlay */}
              <span className="absolute inset-0 overflow-hidden rounded-lg">
                <span className="ask-ai-shimmer absolute inset-0 bg-gradient-to-r from-transparent via-white/50 to-transparent dark:via-violet-300/30"></span>
              </span>
              {/* Sparkles Icon with pulse */}
              <svg className="w-4 h-4 relative z-10 ask-ai-icon" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
              </svg>
              <span className="relative z-10">Ask AI</span>
            </button>

          {incident.status === 'triggered' && (
            <button
              onClick={() => handleAction('acknowledge')}
                disabled={actionLoading !== null}
                className="group relative inline-flex items-center justify-center gap-2 bg-amber-50 hover:bg-amber-100 border border-amber-200 disabled:opacity-50 text-amber-700 hover:text-amber-800 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-amber-300 focus:ring-offset-2 dark:bg-amber-900/20 dark:hover:bg-amber-900/30 dark:border-amber-700/50 dark:text-amber-300 dark:hover:text-amber-200"
            >
                {actionLoading === 'acknowledge' ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    <span>Acknowledge</span>
                  </>
                )}
            </button>
          )}

          {incident.status !== 'resolved' && (
            <button
              onClick={() => handleAction('resolve')}
                disabled={actionLoading !== null}
                className="group relative inline-flex items-center justify-center gap-2 bg-primary-50 hover:bg-primary-100 border border-primary-200 disabled:opacity-50 text-primary-700 hover:text-primary-800 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary-300 focus:ring-offset-2 dark:bg-primary-900/20 dark:hover:bg-primary-900/30 dark:border-primary-700/50 dark:text-primary-300 dark:hover:text-primary-200"
            >
                {actionLoading === 'resolve' ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Resolve</span>
                  </>
                )}
            </button>
          )}

          {incident.status !== 'resolved' && (
            <button
              onClick={() => handleAction('escalate')}
                disabled={actionLoading !== null}
                className="group relative inline-flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 disabled:opacity-50 text-gray-600 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 active:scale-95 dark:bg-gray-700 dark:hover:bg-gray-600 dark:border-gray-600 dark:text-gray-300"
            >
                {actionLoading === 'escalate' ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                    </svg>
                    <span>Escalate</span>
                  </>
                )}
            </button>
          )}
          </div>
        </div>
      </div>

      {/* Incident Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content - Alert Information */}
        <div className="lg:col-span-2 space-y-6">
          {/* Alert Content */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 transition-all duration-200 hover:shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Alert Information
            </h3>

            <div className="space-y-4">
              {/* Alert Title and Description */}
              <div>
                <h4 className="text-base font-medium text-gray-900 dark:text-white mb-2">
                  {incident.title}
                </h4>
                {incident.description && (
                  <MarkdownRenderer
                    content={incident.description}
                    size="base"
                    className="text-sm text-gray-600 dark:text-gray-400"
                  />
                )}
              </div>

              {/* Alert Metadata */}
              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors">
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Severity</dt>
                  <dd className="text-sm font-semibold text-gray-900 dark:text-white mt-1">
                    {incident.severity || 'Unknown'}
                  </dd>
                </div>
                <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors">
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Urgency</dt>
                  <dd className="text-sm font-semibold text-gray-900 dark:text-white mt-1">
                    {incident.urgency || 'Normal'}
                  </dd>
                </div>
                <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors">
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Status</dt>
                  <dd className="text-sm font-semibold text-gray-900 dark:text-white mt-1">
                    {incident.status}
                  </dd>
                </div>
                {incident.source && (
                  <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors">
                    <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Source</dt>
                    <dd className="text-sm font-semibold text-gray-900 dark:text-white mt-1">
                      {incident.source}
                    </dd>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 transition-all duration-200 hover:shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Timeline
            </h3>

            {events.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-center py-8">No events recorded yet.</p>
            ) : (
              <div className="relative">
                {/* Timeline line */}
                <div className="absolute left-[5px] top-2 bottom-2 w-0.5 bg-gray-200 dark:bg-gray-700"></div>
                
              <div className="space-y-4">
                {events.map((event, index) => (
                    <div 
                      key={event.id || index} 
                      className="flex gap-4 group/item"
                      style={{ animationDelay: `${index * 100}ms` }}
                    >
                      <div className="flex-shrink-0 relative z-10">
                        <div className={`w-3 h-3 rounded-full ${getTimelineEventColor(event.event_type)} ring-4 ring-white dark:ring-gray-800 transition-transform duration-200 group-hover/item:scale-125`}></div>
                    </div>
                      <div className="flex-1 pb-4">
                        <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-all duration-200 hover:translate-x-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-semibold text-gray-900 dark:text-white">
                          {event.event_type.replace('_', ' ').toUpperCase()}
                        </span>
                            <span className="text-xs text-gray-400 dark:text-gray-500">
                          {new Date(event.created_at).toLocaleString()}
                        </span>
                      </div>
                      {event.created_by_name && (
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                              by <span className="font-medium text-gray-700 dark:text-gray-300">{event.created_by_name}</span>
                        </p>
                      )}
                      {event.event_data?.note && (
                            <p className="text-sm text-gray-600 dark:text-gray-300 mt-2 pl-3 border-l-2 border-gray-300 dark:border-gray-600">
                          {event.event_data.note}
                        </p>
                      )}
                        </div>
                    </div>
                  </div>
                ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar - Details */}
        <div className="space-y-6">
          {/* Incident Details */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 transition-all duration-200 hover:shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Details
            </h3>

            <div className="space-y-4">
              <div className="group/item">
                <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Incident ID</dt>
                <dd>
                  <CopyButton text={incident.id} label="Incident ID" />
                </dd>
              </div>

              {incident.incident_number && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Incident Number</dt>
                  <dd className="text-sm font-semibold text-gray-900 dark:text-white">
                    #{incident.incident_number}
                  </dd>
                </div>
              )}

              {incident.priority && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Priority</dt>
                  <dd>
                    <span className="px-2 py-1 text-xs font-semibold rounded bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                      {incident.priority}
                    </span>
                  </dd>
                </div>
              )}

              <div>
                <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Created</dt>
                <dd className="text-sm text-gray-900 dark:text-white">
                  {new Date(incident.created_at).toLocaleString()}
                </dd>
              </div>

              {incident.acknowledged_at && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Acknowledged</dt>
                  <dd className="text-sm text-gray-900 dark:text-white">
                    {new Date(incident.acknowledged_at).toLocaleString()}
                  </dd>
                </div>
              )}

              {incident.resolved_at && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Resolved</dt>
                  <dd className="text-sm text-gray-900 dark:text-white">
                    {new Date(incident.resolved_at).toLocaleString()}
                  </dd>
                </div>
              )}

              {incident.assigned_to_name && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Assigned To</dt>
                  <dd className="text-sm font-medium text-gray-900 dark:text-white">
                    {incident.assigned_to_name}
                  </dd>
                </div>
              )}

              {incident.service_name && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Service</dt>
                  <dd className="text-sm text-gray-900 dark:text-white">
                    {incident.service_name}
                  </dd>
                </div>
              )}

              {incident.escalation_policy_name && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Escalation Policy</dt>
                  <dd className="text-sm text-gray-900 dark:text-white">
                    {incident.escalation_policy_name}
                  </dd>
                </div>
              )}

              {incident.current_escalation_level > 0 && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Escalation Level</dt>
                  <dd className="text-sm text-gray-900 dark:text-white flex items-center gap-2">
                    Level {incident.current_escalation_level}
                    {incident.escalation_status && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                        {incident.escalation_status}
                      </span>
                    )}
                  </dd>
                </div>
              )}

              {incident.source && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Source</dt>
                  <dd className="text-sm text-gray-900 dark:text-white">
                    {incident.source}
                  </dd>
                </div>
              )}

              {incident.external_url && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">External Link</dt>
                  <dd>
                    <a
                      href={incident.external_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 transition-colors"
                    >
                      View in source system
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  </dd>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Custom styles for animations */}
      <style jsx>{`
        @keyframes slide-up {
          from {
            opacity: 0;
            transform: translateY(1rem);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          50% {
            transform: translateX(100%);
          }
          100% {
            transform: translateX(100%);
          }
        }
        .ask-ai-shimmer {
          animation: shimmer 3s ease-in-out infinite;
        }
        @keyframes subtle-pulse {
          0%, 100% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 0.7;
            transform: scale(0.95);
          }
        }
        .ask-ai-icon {
          animation: subtle-pulse 2s ease-in-out infinite;
        }
        .ask-ai-btn {
          transition: box-shadow 0.3s ease, transform 0.2s ease;
          box-shadow: 0 2px 8px -2px rgba(139, 92, 246, 0.25), 0 0 0 1px rgba(139, 92, 246, 0.05);
        }
        .ask-ai-btn:hover {
          box-shadow: 0 4px 20px -4px rgba(139, 92, 246, 0.4), 0 0 0 1px rgba(139, 92, 246, 0.1);
          transform: translateY(-2px);
        }
        .ask-ai-btn:hover .ask-ai-icon {
          animation: none;
          transform: scale(1.1);
        }
      `}</style>
    </div>
  );
}
