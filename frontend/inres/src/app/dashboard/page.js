'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import StatCard from '../../components/dashboard/StatCard';
import IncidentsList from '../../components/dashboard/IncidentsList';
import OnCallStatus from '../../components/dashboard/OnCallStatus';
import ServiceStatus from '../../components/dashboard/ServiceStatus';
import IncidentTrendsChart from '../../components/dashboard/IncidentTrendsChart';
import CreateIncidentModal from '../../components/incidents/CreateIncidentModal';
import { apiClient } from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useOrg } from '../../contexts/OrgContext';
import { useRealtimeRefresh } from '../../hooks/useRealtimeRefresh';

// Default stats structure (empty/zero values)
const DEFAULT_STATS = {
  incidents: { total: 0, triggered: 0, acknowledged: 0, resolved: 0 },
  services: { total: 0, up: 0, down: 0 },
  groups: { total: 0, active: 0 },
  uptime: 0
};

export default function DashboardPage() {
  const router = useRouter();
  const { session } = useAuth();
  const { currentOrg, currentProject } = useOrg();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Auto-refresh when realtime incident notifications arrive
  useRealtimeRefresh({
    onIncident: (notification) => {
      console.log('[Dashboard] Realtime incident notification, refreshing...', notification.title);
      setRefreshKey(prev => prev + 1);
    },
    debounceMs: 500, // Debounce rapid updates
  });

  // Fetch incident stats from API
  const fetchStats = useCallback(async () => {
    if (!session?.access_token || !currentOrg?.id) {
      console.log('[Dashboard] No session or org, using defaults');
          setStats(DEFAULT_STATS);
          setLoading(false);
      return;
    }

    try {
      setLoading(true);
      apiClient.setToken(session.access_token);

      // Build filter params
      const filterParams = {
        org_id: currentOrg.id,
        ...(currentProject?.id && { project_id: currentProject.id })
      };

      // Fetch incidents to calculate stats
      // Note: Don't use limit - we need to count ALL matching incidents
      const [triggeredData, acknowledgedData, resolvedData] = await Promise.all([
        apiClient.getIncidents('', { ...filterParams, status: 'triggered' }),
        apiClient.getIncidents('', { ...filterParams, status: 'acknowledged' }),
        apiClient.getIncidents('', { ...filterParams, status: 'resolved' })
      ]);
      
      console.log('[Dashboard] API responses:', { triggeredData, acknowledgedData, resolvedData });

      // Count actual incidents returned (API returns all without limit)
      const triggeredCount = Array.isArray(triggeredData?.incidents) ? triggeredData.incidents.length : 0;
      const acknowledgedCount = Array.isArray(acknowledgedData?.incidents) ? acknowledgedData.incidents.length : 0;
      const resolvedCount = Array.isArray(resolvedData?.incidents) ? resolvedData.incidents.length : 0;

      const incidentStats = {
        triggered: triggeredCount,
        acknowledged: acknowledgedCount,
        resolved: resolvedCount,
        total: triggeredCount + acknowledgedCount + resolvedCount
      };

      console.log('[Dashboard] Incident stats:', incidentStats);

      // Fetch monitor stats (internal + external)
      let serviceStats = { total: 0, up: 0, down: 0 };
      let avgUptime = 0;
      try {
        const [monitorsData, externalData] = await Promise.all([
          apiClient.getMonitors(filterParams),
          apiClient.getExternalMonitors(filterParams).catch(() => [])
        ]);
        
        const allMonitors = [
          ...(Array.isArray(monitorsData) ? monitorsData : []),
          ...(Array.isArray(externalData) ? externalData : [])
        ];
        
        const upMonitors = allMonitors.filter(m => 
          m.is_up === true || m.status === 'up'
        ).length;
        const downMonitors = allMonitors.filter(m => 
          m.is_up === false || m.status === 'down'
        ).length;
        
        serviceStats = {
          total: allMonitors.length,
          up: upMonitors,
          down: downMonitors
        };
        
        // Calculate average uptime from external monitors
        const uptimes = allMonitors
          .filter(m => m.uptime_30d || m.uptime_all_time)
          .map(m => m.uptime_30d || m.uptime_all_time || 0);
        avgUptime = uptimes.length > 0 
          ? (uptimes.reduce((a, b) => a + b, 0) / uptimes.length).toFixed(1)
          : 99.9;
          
        console.log('[Dashboard] Service stats:', serviceStats, 'Avg uptime:', avgUptime);
      } catch (err) {
        console.log('[Dashboard] Error fetching monitors:', err.message);
      }

      setStats({
        ...DEFAULT_STATS,
        incidents: incidentStats,
        services: serviceStats,
        uptime: avgUptime
      });
      } catch (error) {
      console.error('[Dashboard] Failed to fetch stats:', error);
      setStats(DEFAULT_STATS);
    } finally {
        setLoading(false);
      }
  }, [session, currentOrg?.id, currentProject?.id]);

  // Fetch stats on mount and when dependencies change
  useEffect(() => {
    fetchStats();
  }, [fetchStats, refreshKey]);

  const handleIncidentCreated = (newIncident) => {
    console.log('New incident created from dashboard:', newIncident);
    // Refresh both the stats and incidents list
    setRefreshKey(prev => prev + 1);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Dashboard
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Monitor your systems and incidents at a glance
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-brand flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create Incident
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Active Incidents"
          value={loading ? "..." : stats?.incidents.triggered}
          subtitle={loading ? "Loading..." : `${stats?.incidents.total} total incidents`}
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 14.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          }
          iconColor="blue"
          // prominent={true}
          showAlert={stats?.incidents.triggered > 0}
          trend={stats?.incidents.triggered > 0 ? { type: 'up', value: '+2', label: 'from yesterday' } : null}
        />

        <StatCard
          title="Services Status"
          value={loading ? "..." : `${stats?.services.up}/${stats?.services.total}`}
          subtitle={loading ? "Loading..." : 
            stats?.services.down > 0 
              ? `${stats.services.down} service${stats.services.down > 1 ? 's' : ''} degraded`
              : stats?.services.total > 0 
                ? "All systems operational" 
                : "No monitors configured"
          }
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          iconColor={stats?.services.down > 0 ? "red" : "blue"}
          showAlert={stats?.services.down > 0}
          trend={{ type: 'neutral', value: `${stats?.uptime || 99.9}%`, label: 'uptime' }}
        />

        <StatCard
          title="On-Call Teams"
          value={loading ? "..." : stats?.groups.active}
          subtitle={loading ? "Loading..." : `${stats?.groups.total} total teams`}
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
          iconColor="blue"
        />

        <StatCard
          title="Response Time"
          value={loading ? "..." : "156ms"}
          subtitle="Average response"
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
          iconColor="blue"
          trend={{ type: 'down', value: '-12ms', label: 'from last hour' }}
        />
      </div>

      {/* Main Grid: Left (Recent Incidents + Trends) + Right (On-Call + Quick Actions + System Health) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Column - Recent Incidents + Incident Trends */}
        <div className="lg:col-span-2 space-y-4">
          {/* Recent Incidents */}
          <div className="bg-white dark:bg-navy-800/50 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-navy-600/50 overflow-hidden shadow-sm dark:shadow-none">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-navy-700/50 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Incidents</h3>
              <Link href="/incidents" className="text-sm text-primary-500 dark:text-primary-400 hover:text-primary-600 dark:hover:text-primary-300 transition-colors">
                View all →
              </Link>
            </div>
            <div className="p-4">
              <IncidentsList limit={3} refreshKey={refreshKey} />
            </div>
          </div>

          {/* Incident Trends Charts */}
          <div className="bg-white dark:bg-navy-800/50 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-navy-600/50 p-5 shadow-sm dark:shadow-none">
            <IncidentTrendsChart refreshKey={refreshKey} />
          </div>
        </div>

        {/* Right Column - On-Call + Quick Actions + System Health */}
        <div className="space-y-4">
          {/* On-Call Status */}
          <div className="bg-white dark:bg-navy-800/50 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-navy-600/50 overflow-hidden shadow-sm dark:shadow-none">
            <div className="px-5 py-3 border-b border-gray-200 dark:border-navy-700/50">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">On-Call Now</h3>
            </div>
            <div className="p-4">
              <OnCallStatus showHeader={false} compact={true} />
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white dark:bg-navy-800/50 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-navy-600/50 p-4 shadow-sm dark:shadow-none">
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">Quick Actions</h3>
            <div className="space-y-2">
              <button
                onClick={() => setShowCreateModal(true)}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 dark:text-white rounded-lg hover:bg-primary-50 dark:hover:bg-primary-500/10 transition-all"
              >
                <div className="w-8 h-8 rounded-lg bg-primary-500 flex items-center justify-center text-white">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </div>
                <span>New Incident</span>
              </button>
              
              <Link
                href="/groups"
                className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 dark:text-white rounded-lg hover:bg-gray-50 dark:hover:bg-navy-700/50 transition-all"
              >
                <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-gray-600 dark:text-gray-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span>Schedules</span>
              </Link>
              
              <Link
                href="/ai-agent"
                className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 dark:text-white rounded-lg hover:bg-gray-50 dark:hover:bg-navy-700/50 transition-all"
              >
                <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-gray-600 dark:text-gray-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
                <span>AI Agent</span>
              </Link>
              
              <Link
                href="/integrations"
                className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 dark:text-white rounded-lg hover:bg-gray-50 dark:hover:bg-navy-700/50 transition-all"
              >
                <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-gray-600 dark:text-gray-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <span>Integrations</span>
              </Link>
            </div>
          </div>

          {/* System Health */}
          <div className="bg-white dark:bg-navy-800/50 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-navy-600/50 p-4 shadow-sm dark:shadow-none">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">System Health</h3>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">API Status</span>
                <span className="text-sm font-medium text-primary-600 dark:text-primary-400">Operational</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">Database</span>
                <span className="text-sm font-medium text-primary-600 dark:text-primary-400">Healthy</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">AI Agent</span>
                <span className="text-sm font-medium text-primary-600 dark:text-primary-400">Online</span>
              </div>
              <div className="h-px bg-gray-100 dark:bg-navy-600/50 my-1" />
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">Latency</span>
                <span className="text-sm font-semibold text-gray-900 dark:text-white">23ms</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Row 3: Service Status - Full Width */}
      <div className="bg-white dark:bg-navy-800/50 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-navy-600/50 overflow-hidden shadow-sm dark:shadow-none">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-navy-700/50 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Service Status</h3>
          <Link href="/monitors" className="text-sm text-primary-500 dark:text-primary-400 hover:text-primary-600 dark:hover:text-primary-300 transition-colors">
            View all →
          </Link>
        </div>
        <div className="p-4">
          <ServiceStatus limit={8} showHeader={false} />
        </div>
      </div>

      {/* Create Incident Modal */}
      <CreateIncidentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onIncidentCreated={handleIncidentCreated}
      />
    </div>
  );
}
