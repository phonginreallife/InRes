'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiClient } from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useOrg } from '../../contexts/OrgContext';

// ============================================
// CONFIGURATION
// ============================================

const severityConfig = {
  critical: {
    bg: 'bg-red-500/10 dark:bg-red-500/20',
    bgHover: 'hover:bg-red-500/15 dark:hover:bg-red-500/25',
    border: 'border-red-500/30 dark:border-red-500/40',
    indicator: 'bg-red-500',
    badge: 'bg-red-500 text-white',
    badgeGlow: 'shadow-red-500/50 shadow-lg',
    text: 'text-red-600 dark:text-red-400',
    label: 'CRITICAL',
    weight: 4,
    pulse: true
  },
  high: {
    bg: 'bg-orange-500/5 dark:bg-orange-500/10',
    bgHover: 'hover:bg-orange-500/10 dark:hover:bg-orange-500/15',
    border: 'border-orange-500/20 dark:border-orange-500/30',
    indicator: 'bg-orange-500',
    badge: 'bg-orange-500 text-white',
    badgeGlow: 'shadow-orange-500/30',
    text: 'text-orange-600 dark:text-orange-400',
    label: 'HIGH',
    weight: 3,
    pulse: false
  },
  medium: {
    bg: 'bg-amber-500/5 dark:bg-amber-500/10',
    bgHover: 'hover:bg-amber-500/8 dark:hover:bg-amber-500/12',
    border: 'border-amber-500/15 dark:border-amber-500/25',
    indicator: 'bg-amber-500',
    badge: 'bg-amber-500 text-white',
    badgeGlow: '',
    text: 'text-amber-600 dark:text-amber-400',
    label: 'MEDIUM',
    weight: 2,
    pulse: false
  },
  low: {
    bg: 'bg-slate-500/5 dark:bg-slate-500/10',
    bgHover: 'hover:bg-slate-500/8 dark:hover:bg-slate-500/12',
    border: 'border-slate-500/15 dark:border-slate-400/20',
    indicator: 'bg-slate-400 dark:bg-slate-500',
    badge: 'bg-slate-500 dark:bg-slate-600 text-white',
    badgeGlow: '',
    text: 'text-slate-600 dark:text-slate-400',
    label: 'LOW',
    weight: 1,
    pulse: false
  }
};

const statusConfig = {
  triggered: {
    bg: 'bg-red-100 dark:bg-red-500/20',
    text: 'text-red-700 dark:text-red-300',
    border: 'border-red-200 dark:border-red-500/30',
    icon: 'fire',
    label: 'OPEN',
    pulse: true,
    priority: 3
  },
  acknowledged: {
    bg: 'bg-amber-100 dark:bg-amber-500/20',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-500/30',
    icon: 'eye',
    label: 'ACK',
    pulse: false,
    priority: 2
  },
  resolved: {
    bg: 'bg-emerald-100 dark:bg-emerald-500/20',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-200 dark:border-emerald-500/30',
    icon: 'check',
    label: 'RESOLVED',
    pulse: false,
    priority: 1
  }
};

const defaultSeverity = {
  bg: 'bg-gray-50 dark:bg-gray-800/50',
  bgHover: 'hover:bg-gray-100 dark:hover:bg-gray-800',
  border: 'border-gray-200 dark:border-gray-700',
  indicator: 'bg-gray-400',
  badge: 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
  badgeGlow: '',
  text: 'text-gray-600 dark:text-gray-400',
  label: 'UNKNOWN',
  weight: 0,
  pulse: false
};

// ============================================
// UTILITY FUNCTIONS
// ============================================

function getSeverityStyle(severity) {
  return severityConfig[severity] || defaultSeverity;
}

function getStatusStyle(status) {
  return statusConfig[status] || statusConfig.triggered;
}

/**
 * Enhanced time formatting with urgency indicators
 */
function formatTimeWithUrgency(timeString, status) {
  const now = Date.now();
  const then = new Date(timeString).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  // Determine urgency level based on how long incident has been unresolved
  let urgency = 'normal'; // normal, warning, critical
  if (status !== 'resolved') {
    if (diffMins >= 60) urgency = 'warning';
    if (diffMins >= 120) urgency = 'critical';
  }

  let text = '';
  let shortText = '';

  if (diffMins < 1) {
    text = 'Just now';
    shortText = 'Now';
  } else if (diffMins < 60) {
    text = `${diffMins}m ago`;
    shortText = `${diffMins}m`;
  } else if (diffHours < 24) {
    const remainingMins = diffMins % 60;
    if (status !== 'resolved' && diffMins >= 60) {
      text = `${diffHours}h ${remainingMins}m unresolved`;
      shortText = `${diffHours}h ${remainingMins}m`;
    } else {
      text = `${diffHours}h ago`;
      shortText = `${diffHours}h`;
    }
  } else {
    text = `${diffDays}d ago`;
    shortText = `${diffDays}d`;
  }

  return { text, shortText, urgency, diffMins };
}

/**
 * Get urgency color classes
 */
function getUrgencyColor(urgency) {
  switch (urgency) {
    case 'critical':
      return 'text-red-600 dark:text-red-400 font-semibold';
    case 'warning':
      return 'text-amber-600 dark:text-amber-400 font-medium';
    default:
      return 'text-gray-500 dark:text-gray-400';
  }
}

// ============================================
// ICONS
// ============================================

const StatusIcon = ({ status, className = "w-3.5 h-3.5" }) => {
  const config = getStatusStyle(status);
  
  switch (config.icon) {
    case 'fire':
      return (
        <svg className={className} fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z" clipRule="evenodd" />
        </svg>
      );
    case 'eye':
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      );
    case 'check':
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      );
    default:
      return null;
  }
};

const ActionIcon = ({ type, className = "w-4 h-4" }) => {
  switch (type) {
    case 'acknowledge':
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      );
    case 'assign':
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
        </svg>
      );
    case 'snooze':
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case 'timeline':
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
      );
    default:
      return null;
  }
};

// ============================================
// TRIAGE ACTION BUTTONS
// ============================================

function TriageActions({ incident, onAction, compact = false }) {
  const router = useRouter();
  const [loadingAction, setLoadingAction] = useState(null);
  
  const handleAction = async (action, e) => {
    e.preventDefault();
    e.stopPropagation();
    setLoadingAction(action);
    try {
      await onAction(action, incident);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleTimelineClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    router.push(`/incidents/${incident.id}#timeline`);
  };

  const isTriggered = incident.status === 'triggered';
  const isResolved = incident.status === 'resolved';

  const buttonBase = compact
    ? "p-1.5 rounded-md transition-all duration-150"
    : "flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all duration-150";

  return (
    <div className={`flex items-center ${compact ? 'gap-1' : 'gap-2'}`}>
      {/* Acknowledge - only for triggered */}
      {isTriggered && (
        <button
          onClick={(e) => handleAction('acknowledge', e)}
          disabled={loadingAction === 'acknowledge'}
          className={`${buttonBase} bg-amber-100 hover:bg-amber-200 text-amber-700 dark:bg-amber-500/20 dark:hover:bg-amber-500/30 dark:text-amber-300`}
          title="Acknowledge (A)"
        >
          {loadingAction === 'acknowledge' ? (
            <span className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <ActionIcon type="acknowledge" />
              {!compact && <span>Ack</span>}
            </>
          )}
        </button>
      )}

      {/* Assign - for triggered or acknowledged */}
      {!isResolved && (
        <button
          onClick={(e) => handleAction('assign', e)}
          disabled={loadingAction === 'assign'}
          className={`${buttonBase} bg-blue-100 hover:bg-blue-200 text-blue-700 dark:bg-blue-500/20 dark:hover:bg-blue-500/30 dark:text-blue-300`}
          title="Assign (S)"
        >
          {loadingAction === 'assign' ? (
            <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <ActionIcon type="assign" />
              {!compact && <span>Assign</span>}
            </>
          )}
        </button>
      )}

      {/* Snooze - for triggered or acknowledged */}
      {!isResolved && (
        <button
          onClick={(e) => handleAction('snooze', e)}
          disabled={loadingAction === 'snooze'}
          className={`${buttonBase} bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-300`}
          title="Snooze (Z)"
        >
          {loadingAction === 'snooze' ? (
            <span className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <ActionIcon type="snooze" />
              {!compact && <span>Snooze</span>}
            </>
          )}
        </button>
      )}

      {/* View Timeline - using button to avoid nested <a> tags */}
      <button
        onClick={handleTimelineClick}
        className={`${buttonBase} bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-300`}
        title="View Timeline (T)"
      >
        <ActionIcon type="timeline" />
        {!compact && <span>Timeline</span>}
      </button>
    </div>
  );
}

// ============================================
// INCIDENT ROW COMPONENT
// ============================================

function IncidentRow({ incident, isCompact, onTriageAction, index }) {
  const [isHovered, setIsHovered] = useState(false);
  
  const severity = getSeverityStyle(incident.severity);
  const status = getStatusStyle(incident.status);
  const timeInfo = formatTimeWithUrgency(incident.created_at, incident.status);
  const isResolved = incident.status === 'resolved';
  const isCritical = incident.severity === 'critical';
  const isTriggered = incident.status === 'triggered';

  // Compact row - optimized for density
  // Resolved incidents get muted styling regardless of severity
  const compactBg = isResolved 
    ? 'bg-gray-50 dark:bg-gray-800/30' 
    : severity.bg;
  const compactBgHover = isResolved 
    ? 'hover:bg-gray-100 dark:hover:bg-gray-800/50' 
    : severity.bgHover;
  const compactBorder = isResolved 
    ? 'border-gray-200 dark:border-gray-700/50' 
    : severity.border;

  if (isCompact) {
    return (
      <Link
        href={`/incidents/${incident.id}`}
        className={`
          group flex items-center gap-3 px-3 py-2.5
          rounded-lg border transition-all duration-150
          ${compactBg} ${compactBgHover} ${compactBorder}
          ${isResolved ? 'opacity-70 hover:opacity-100' : ''}
        `}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ 
          animationName: 'fadeSlideIn',
          animationDuration: '0.2s',
          animationTimingFunction: 'ease-out',
          animationFillMode: 'forwards',
          animationDelay: `${index * 30}ms`
        }}
      >
        {/* Severity indicator - muted for resolved */}
        <div className={`w-1 h-8 rounded-full ${isResolved ? 'bg-gray-300 dark:bg-gray-600' : severity.indicator} ${severity.pulse && isTriggered ? 'animate-pulse' : ''}`} />
        
        {/* Status badge */}
        <div className={`flex-shrink-0 flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${status.bg} ${status.text} ${status.border} border`}>
          {status.pulse && (
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-red-500"></span>
            </span>
          )}
          <StatusIcon status={incident.status} className="w-3 h-3" />
          <span>{status.label}</span>
        </div>

        {/* Severity badge */}
        <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${isResolved ? 'bg-gray-400 dark:bg-gray-600 text-white' : severity.badge} ${isResolved ? '' : severity.badgeGlow}`}>
          {severity.label}
        </span>

        {/* Title */}
        <span className="flex-1 min-w-0 text-sm font-medium text-gray-900 dark:text-white truncate group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors font-display">
          {incident.title}
        </span>

        {/* Time */}
        <span className={`flex-shrink-0 text-xs ${getUrgencyColor(timeInfo.urgency)}`}>
          {timeInfo.shortText}
        </span>

        {/* Hover actions */}
        {isHovered && !isResolved && (
          <div className="flex-shrink-0 animate-fade-in">
            <TriageActions incident={incident} onAction={onTriageAction} compact={true} />
          </div>
        )}

        {/* Arrow */}
        <svg className="flex-shrink-0 w-4 h-4 text-gray-400 group-hover:text-primary-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </Link>
    );
  }

  // Detailed row - full information
  // Resolved incidents get muted styling regardless of severity
  const rowBg = isResolved 
    ? 'bg-gray-50 dark:bg-gray-800/30' 
    : severity.bg;
  const rowBgHover = isResolved 
    ? 'hover:bg-gray-100 dark:hover:bg-gray-800/50' 
    : severity.bgHover;
  const rowBorder = isResolved 
    ? 'border-gray-200 dark:border-gray-700/50' 
    : severity.border;

  return (
    <Link
      href={`/incidents/${incident.id}`}
      className={`
        group relative block overflow-hidden
        rounded-xl border-2 transition-all duration-200
        ${rowBg} ${rowBgHover} ${rowBorder}
        ${isResolved ? 'opacity-70 hover:opacity-100' : ''}
        ${isCritical && isTriggered ? 'ring-2 ring-red-500/50 ring-offset-2 ring-offset-white dark:ring-offset-navy-900' : ''}
      `}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{ 
        animationName: 'fadeSlideIn',
        animationDuration: '0.25s',
        animationTimingFunction: 'ease-out',
        animationFillMode: 'forwards',
        animationDelay: `${index * 40}ms`
      }}
    >
      {/* Left severity bar - muted for resolved */}
      <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${isResolved ? 'bg-gray-300 dark:bg-gray-600' : severity.indicator} ${severity.pulse && isTriggered ? 'animate-pulse' : ''}`} />

      {/* Critical incident pulse overlay */}
      {isCritical && isTriggered && (
        <div className="absolute inset-0 bg-red-500/5 animate-pulse pointer-events-none" />
      )}

      <div className="pl-5 pr-4 py-4">
        {/* Top row: Status + Severity + Title + Time */}
        <div className="flex items-start gap-3">
          {/* Status + Severity cluster */}
          <div className="flex-shrink-0 flex flex-col gap-1.5">
            {/* Status badge - PRIMARY signal */}
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wide ${status.bg} ${status.text} ${status.border} border`}>
              {status.pulse && (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                </span>
              )}
              <StatusIcon status={incident.status} className="w-3.5 h-3.5" />
              <span>{status.label}</span>
            </div>
            
            {/* Severity badge */}
            <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${isResolved ? 'bg-gray-400 dark:bg-gray-600 text-white' : severity.badge} ${isResolved ? '' : severity.badgeGlow}`}>
              {severity.label}
            </span>
          </div>

          {/* Title + Meta */}
          <div className="flex-1 min-w-0">
            <h4 className="text-base font-semibold text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors line-clamp-2 font-display tracking-tight">
              {incident.title}
            </h4>

            {/* Meta row */}
            <div className="flex items-center flex-wrap gap-x-4 gap-y-1 mt-2">
              {/* Time with urgency */}
              <div className={`flex items-center gap-1.5 ${getUrgencyColor(timeInfo.urgency)}`}>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-xs">{timeInfo.text}</span>
                {timeInfo.urgency === 'critical' && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 font-medium">
                    OVERDUE
                  </span>
                )}
              </div>

              {/* Source */}
              <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
                <span className="font-medium">{incident.source || 'manual'}</span>
              </div>

              {/* Assignee */}
              {incident.assigned_to_name && (
                <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <span className="font-medium">{incident.assigned_to_name}</span>
                </div>
              )}

              {/* Resolved by */}
              {incident.resolved_by_name && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-medium">{incident.resolved_by_name}</span>
                </div>
              )}
            </div>
          </div>

          {/* Right side: Actions (on hover) or Arrow */}
          <div className="flex-shrink-0 flex items-center">
            {isHovered && !isResolved ? (
              <div className="animate-fade-in">
                <TriageActions incident={incident} onAction={onTriageAction} compact={false} />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-700/50 flex items-center justify-center group-hover:bg-primary-100 dark:group-hover:bg-primary-900/30 transition-colors">
                <svg className="w-4 h-4 text-gray-400 group-hover:text-primary-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}

// ============================================
// DENSITY TOGGLE
// ============================================

function DensityToggle({ isCompact, onToggle }) {
  return (
    <div className="flex items-center gap-1 p-0.5 rounded-lg bg-gray-100 dark:bg-gray-800">
      <button
        onClick={() => onToggle(false)}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
          !isCompact 
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' 
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
        }`}
        title="Detailed view"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
        <span className="hidden sm:inline">Detailed</span>
      </button>
      <button
        onClick={() => onToggle(true)}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
          isCompact 
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' 
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
        }`}
        title="Compact view"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <span className="hidden sm:inline">Compact</span>
      </button>
    </div>
  );
}

// ============================================
// SUMMARY BAR
// ============================================

function IncidentSummaryBar({ incidents }) {
  const summary = useMemo(() => {
    const criticalCount = incidents.filter(i => i.severity === 'critical' && i.status === 'triggered').length;
    const highCount = incidents.filter(i => i.severity === 'high' && i.status === 'triggered').length;
    const triggeredCount = incidents.filter(i => i.status === 'triggered').length;
    const acknowledgedCount = incidents.filter(i => i.status === 'acknowledged').length;
    
    return { criticalCount, highCount, triggeredCount, acknowledgedCount };
  }, [incidents]);

  if (summary.triggeredCount === 0 && summary.acknowledgedCount === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 mb-3">
      {summary.criticalCount > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
          </span>
          <span className="text-xs font-bold text-red-600 dark:text-red-400">
            {summary.criticalCount} Critical
          </span>
        </div>
      )}
      {summary.highCount > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-orange-500" />
          <span className="text-xs font-medium text-orange-600 dark:text-orange-400">
            {summary.highCount} High
          </span>
        </div>
      )}
      {summary.triggeredCount > 0 && (
        <div className="flex items-center gap-1.5 ml-auto">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {summary.triggeredCount} open
          </span>
        </div>
      )}
      {summary.acknowledgedCount > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {summary.acknowledgedCount} acknowledged
          </span>
        </div>
      )}
    </div>
  );
}

// ============================================
// MAIN COMPONENT
// ============================================

export default function IncidentsList({ 
  limit = 5, 
  refreshKey = 0,
  showDensityToggle = true,
  defaultCompact = false,
  showSummary = true
}) {
  const { session } = useAuth();
  const { currentOrg, currentProject } = useOrg();
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isCompact, setIsCompact] = useState(defaultCompact);
  const [actionError, setActionError] = useState(null);

  // Fetch incidents
  useEffect(() => {
    const fetchIncidents = async () => {
      setLoading(true);
      setError(null);

      if (!session?.access_token) {
        setIncidents([]);
        setLoading(false);
        return;
      }

      if (!currentOrg?.id) {
        setIncidents([]);
        setLoading(false);
        return;
      }

      try {
        apiClient.setToken(session.access_token);
        
        const filterParams = {
          org_id: currentOrg.id,
          ...(currentProject?.id && { project_id: currentProject.id })
        };
        
        const data = await apiClient.getRecentIncidents(limit, filterParams);
        
        // Sort: triggered first, then by severity weight, then by time
        const sorted = (data.incidents || []).sort((a, b) => {
          const statusA = getStatusStyle(a.status).priority;
          const statusB = getStatusStyle(b.status).priority;
          if (statusB !== statusA) return statusB - statusA;
          
          const sevA = getSeverityStyle(a.severity).weight;
          const sevB = getSeverityStyle(b.severity).weight;
          if (sevB !== sevA) return sevB - sevA;
          
          return new Date(b.created_at) - new Date(a.created_at);
        });
        
        setIncidents(sorted);
      } catch (err) {
        console.error('[IncidentsList] Error fetching incidents:', err);
        setError(err.message);
        setIncidents([]);
      } finally {
        setLoading(false);
      }
    };

    fetchIncidents();
  }, [limit, session, currentOrg?.id, currentProject?.id, refreshKey]);

  // Handle triage actions
  const handleTriageAction = useCallback(async (action, incident) => {
    if (!session?.access_token || !currentOrg?.id) return;
    
    setActionError(null);
    apiClient.setToken(session.access_token);
    
    const filterParams = {
      org_id: currentOrg.id,
      ...(currentProject?.id && { project_id: currentProject.id })
    };

    try {
      switch (action) {
        case 'acknowledge':
          await apiClient.acknowledgeIncident(incident.id, '', filterParams);
          // Update local state
          setIncidents(prev => prev.map(i => 
            i.id === incident.id ? { ...i, status: 'acknowledged' } : i
          ));
          break;
        case 'assign':
          // TODO: Open assign modal
          console.log('Assign action for:', incident.id);
          break;
        case 'snooze':
          // TODO: Open snooze modal
          console.log('Snooze action for:', incident.id);
          break;
      }
    } catch (err) {
      console.error(`[IncidentsList] ${action} failed:`, err);
      setActionError(`Failed to ${action}: ${err.message}`);
    }
  }, [session, currentOrg?.id, currentProject?.id]);

  // Loading state
  if (loading) {
    return (
      <div className="space-y-3">
        {showDensityToggle && (
          <div className="flex justify-end mb-2">
            <div className="h-8 w-40 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
          </div>
        )}
        {[1, 2, 3].map((i) => (
          <div 
            key={i} 
            className={`relative overflow-hidden rounded-xl border border-gray-100 dark:border-gray-700/50 bg-white dark:bg-gray-800/50 ${isCompact ? 'py-2.5 px-3' : 'py-4 px-5'}`}
          >
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-8 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse" />
              <div className="w-16 h-6 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
              <div className="w-12 h-5 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
              <div className="flex-1 h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
              <div className="w-12 h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-8 px-4 rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20">
        <svg className="w-8 h-8 mx-auto text-red-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm font-medium text-red-600 dark:text-red-400">Failed to load incidents</p>
        <p className="text-xs text-red-500 dark:text-red-400/70 mt-1">{error}</p>
      </div>
    );
  }

  // Empty state
  if (!incidents.length) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-green-100 dark:from-emerald-900/30 dark:to-green-900/30 mb-4">
          <svg className="w-8 h-8 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white font-display tracking-tight">All Systems Operational</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">No active incidents at this time</p>
      </div>
    );
  }

  return (
    <div>
      {/* Header with density toggle */}
      {showDensityToggle && (
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
            {incidents.length} incident{incidents.length !== 1 ? 's' : ''}
                    </span>
          <DensityToggle isCompact={isCompact} onToggle={setIsCompact} />
                  </div>
      )}

      {/* Summary bar */}
      {showSummary && <IncidentSummaryBar incidents={incidents} />}

      {/* Action error */}
      {actionError && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20">
          <p className="text-xs text-red-600 dark:text-red-400">{actionError}</p>
        </div>
      )}

      {/* Incident list */}
      <div className={isCompact ? 'space-y-1.5' : 'space-y-3'}>
        {incidents.map((incident, index) => (
          <IncidentRow
            key={incident.id}
            incident={incident}
            isCompact={isCompact}
            onTriageAction={handleTriageAction}
            index={index}
          />
        ))}
            </div>

      {/* Animation styles */}
      <style jsx>{`
        @keyframes fadeSlideIn {
          from {
            opacity: 0;
            transform: translateY(4px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
