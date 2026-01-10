'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiClient } from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useOrg } from '../../contexts/OrgContext';

function formatTimeUntil(timeString) {
  if (!timeString) return '—';
  const target = new Date(timeString);
  const now = new Date();
  const diffMs = target - now;
  
  if (diffMs < 0) return 'Ended';
  
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  
  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export default function OnCallStatus({ showHeader = true }) {
  const { session, user } = useAuth();
  const { currentOrg } = useOrg();
  const [onCallData, setOnCallData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchOnCallStatus = async () => {
      if (!session?.access_token || !currentOrg?.id) {
        setOnCallData([]);
        setLoading(false);
        return;
      }

      try {
        apiClient.setToken(session.access_token);
        
        // First get all groups
        const groupsData = await apiClient.getGroups({ org_id: currentOrg.id });
        const groups = Array.isArray(groupsData) ? groupsData : (groupsData?.groups || []);
        
        if (groups.length === 0) {
          setOnCallData([]);
          setLoading(false);
          return;
        }

        // Fetch current on-call for each group
        const onCallPromises = groups.map(async (group) => {
          try {
            const currentOnCall = await apiClient.getCurrentOnCall(group.id, { org_id: currentOrg.id });
            return {
              group_id: group.id,
              group_name: group.name,
              current_oncall: currentOnCall?.current_oncall || currentOnCall,
              message: currentOnCall?.message
            };
          } catch (err) {
            // Group has no on-call configured
            return {
              group_id: group.id,
              group_name: group.name,
              current_oncall: null,
              message: 'No schedule'
            };
          }
        });

        const results = await Promise.all(onCallPromises);
        // Filter to only groups with active on-call
        const activeOnCall = results.filter(r => r.current_oncall);
        setOnCallData(activeOnCall);
        setError(null);
      } catch (err) {
        console.error('[OnCallStatus] Error:', err);
        setError(err.message);
        setOnCallData([]);
      } finally {
        setLoading(false);
      }
    };

    fetchOnCallStatus();
  }, [session?.access_token, currentOrg?.id]);

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-5 bg-gray-200 dark:bg-navy-600 rounded w-2/3"></div>
        <div className="h-20 bg-gray-100 dark:bg-navy-700/50 rounded-xl"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">Unable to load on-call status</p>
      </div>
    );
  }

  if (!onCallData.length) {
    return (
      <div className="text-center py-6">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-gray-100 dark:bg-navy-700 mb-2">
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400">No active on-call schedules</p>
        <Link href="/groups" className="text-xs text-primary-600 dark:text-primary-400 hover:underline mt-1 inline-block">
          Set up on-call →
        </Link>
      </div>
    );
  }

  // Check if current user is on-call in any group
  const userOnCall = onCallData.find(d => 
    d.current_oncall?.user_id === user?.id || 
    d.current_oncall?.user_email === user?.email
  );

  return (
    <div className="space-y-4">
      {/* Current user status */}
      <div className="flex items-center gap-2">
        <div className={`w-2.5 h-2.5 rounded-full ${userOnCall ? 'bg-primary-500 animate-pulse' : 'bg-gray-400'}`} />
        <span className={`text-sm font-medium ${userOnCall ? 'text-primary-600 dark:text-primary-400' : 'text-gray-500 dark:text-gray-400'}`}>
          {userOnCall ? 'You are currently on-call' : 'Not on-call'}
        </span>
      </div>

      {/* On-call list by group */}
      <div className="space-y-2">
        {onCallData.map((item) => (
          <div 
            key={item.group_id}
            className="p-3 rounded-xl bg-white dark:bg-navy-700/30 border border-gray-100 dark:border-navy-600/50"
          >
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  {item.group_name}
                </p>
                <p className="text-sm font-semibold text-gray-900 dark:text-white truncate mt-0.5">
                  {item.current_oncall?.user_name || item.current_oncall?.user_email || 'Unknown'}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-400 dark:text-gray-500">Ends in</p>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {formatTimeUntil(item.current_oncall?.end_time)}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
