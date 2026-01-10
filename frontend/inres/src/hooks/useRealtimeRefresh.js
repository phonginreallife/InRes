'use client';

import { useEffect, useRef } from 'react';
import { useNotifications } from '../contexts/NotificationContext';

/**
 * Hook to trigger a callback when specific real-time events occur
 * Useful for refreshing dashboard data when incidents/alerts change
 */
export function useRealtimeRefresh({
  onIncident,
  onAlert,
  onService,
  onAny,
  debounceMs = 300
} = {}) {
  const { notifications } = useNotifications();
  const lastProcessedRef = useRef(null);
  const debounceTimerRef = useRef(null);
  
  // Store callbacks in refs to avoid stale closures
  const callbacksRef = useRef({ onIncident, onAlert, onService, onAny });
  callbacksRef.current = { onIncident, onAlert, onService, onAny };

  const latestNotification = notifications[0];

  useEffect(() => {
    if (!latestNotification) return;
    if (lastProcessedRef.current === latestNotification.id) return;

    console.log('[useRealtimeRefresh] New notification:', latestNotification.type, latestNotification.title);
    lastProcessedRef.current = latestNotification.id;

    // Clear any pending debounce
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Debounce the callback
    debounceTimerRef.current = setTimeout(() => {
      const { onIncident, onAlert, onService, onAny } = callbacksRef.current;
      
      console.log('[useRealtimeRefresh] Triggering refresh for:', latestNotification.type);
      
      switch (latestNotification.type) {
        case 'incident':
          onIncident?.(latestNotification);
          break;
        case 'alert':
          onAlert?.(latestNotification);
          break;
        case 'service':
          onService?.(latestNotification);
          break;
      }
      onAny?.(latestNotification);
    }, debounceMs);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [latestNotification, debounceMs]);

  return { latestNotification };
}

export default useRealtimeRefresh;
