'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { initSupabase } from '../lib/supabase';
import { useAuth } from './AuthContext';
import { useOrg } from './OrgContext';

// Types
export interface RealtimeNotification {
  id: string;
  type: 'incident' | 'alert' | 'escalation' | 'service' | 'system';
  eventType: 'INSERT' | 'UPDATE' | 'DELETE';
  title: string;
  message: string;
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info';
  data?: any;
  read: boolean;
  timestamp: Date;
  link?: string;
}

interface NotificationContextValue {
  notifications: RealtimeNotification[];
  unreadCount: number;
  isConnected: boolean;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearNotification: (id: string) => void;
  clearAll: () => void;
  // Broadcast a notification to all connected clients in the same org
  broadcastIncident: (incident: any, eventType?: string) => Promise<void>;
  // Test function
  testNotification: () => void;
}

const defaultContextValue: NotificationContextValue = {
  notifications: [],
  unreadCount: 0,
  isConnected: false,
  markAsRead: () => {},
  markAllAsRead: () => {},
  clearNotification: () => {},
  clearAll: () => {},
  broadcastIncident: async () => {},
  testNotification: () => {},
};

const NotificationContext = createContext<NotificationContextValue>(defaultContextValue);

export const useNotifications = (): NotificationContextValue => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};

interface NotificationProviderProps {
  children: ReactNode;
}

export const NotificationProvider = ({ children }: NotificationProviderProps) => {
  const [notifications, setNotifications] = useState<RealtimeNotification[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const { user, session } = useAuth();
  const { currentOrg } = useOrg();

  const unreadCount = notifications.filter((n) => !n.read).length;

  // Add notification to state (popup shown from NotificationBell component)
  const addNotification = useCallback(
    (notification: RealtimeNotification) => {
      setNotifications((prev) => {
        // Avoid duplicates
        if (prev.some((n) => n.id === notification.id)) {
          return prev;
        }
        // Keep max 50 notifications
        const updated = [notification, ...prev].slice(0, 50);
        return updated;
      });
    },
    []
  );

  // Mark notification as read
  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  // Mark all as read
  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  // Clear single notification
  const clearNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  // Clear all notifications
  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  // Channel reference for broadcasting
  const channelRef = React.useRef<any>(null);

  // Broadcast an incident notification to all connected clients
  const broadcastIncident = useCallback(async (incident: any, eventType: string = 'INSERT') => {
    if (!channelRef.current) {
      console.warn('Cannot broadcast: channel not connected');
      return;
    }

    console.log('📢 Broadcasting incident:', eventType, incident.title);
    
    await channelRef.current.send({
      type: 'broadcast',
      event: 'incident',
      payload: { data: incident, eventType },
    });
  }, []);

  // Test notification function
  const testNotification = useCallback(() => {
    const testIncident = {
      id: `test-${Date.now()}`,
      title: 'Test Notification',
      description: 'This is a test notification to verify real-time is working',
      severity: 'medium',
      status: 'triggered',
    };

    const notification: RealtimeNotification = {
      id: `test-${Date.now()}`,
      type: 'incident',
      eventType: 'INSERT',
      title: '🧪 Test Notification',
      message: 'Real-time notifications are working!',
      severity: 'info',
      data: testIncident,
      read: false,
      timestamp: new Date(),
    };

    addNotification(notification);
    console.log('  Test notification added');
  }, [addNotification]);

  // Subscribe to Supabase realtime
  useEffect(() => {
    if (!user || !session?.access_token || !currentOrg?.id) {
      return;
    }

    let channel: any = null;

    const setupRealtime = async () => {
      try {
        const supabase = await initSupabase();

        console.log('🔌 Setting up realtime for org:', currentOrg.id, 'user:', user.id);

        // Create a unique channel for this organization
        // Using Supabase Broadcast for reliable real-time notifications
        channel = supabase
          .channel(`org-notifications-${currentOrg.id}`, {
            config: {
              broadcast: { self: true }, // Receive own broadcasts for testing
            },
          })
          // Listen for broadcast events (sent by API when incidents are created/updated)
          .on('broadcast', { event: 'incident' }, (payload: any) => {
            console.log('🔔 Broadcast incident event:', payload);
            
            const { data, eventType } = payload.payload || {};
            if (!data) return;

            const notification: RealtimeNotification = {
              id: `incident-${data.id}-${Date.now()}`,
              type: 'incident',
              eventType: eventType || 'INSERT',
              title: data.title || 'Incident',
              message: getIncidentMessage(eventType || 'INSERT', data),
              severity: data.severity || 'medium',
              data: data,
              read: false,
              timestamp: new Date(),
              link: `/incidents/${data.id}`,
            };

            addNotification(notification);
          })
          .on('broadcast', { event: 'alert' }, (payload: any) => {
            console.log('🔔 Broadcast alert event:', payload);
            
            const { data } = payload.payload || {};
            if (!data) return;

            const notification: RealtimeNotification = {
              id: `alert-${data.id}-${Date.now()}`,
              type: 'alert',
              eventType: 'INSERT',
              title: data.title || 'New Alert',
              message: data.description || 'A new alert has been received',
              severity: data.severity || 'medium',
              data: data,
              read: false,
              timestamp: new Date(),
              link: `/alerts/${data.id}`,
            };

            addNotification(notification);
          })
          .on('broadcast', { event: 'monitor' }, (payload: any) => {
            console.log('🔔 Broadcast monitor event:', payload);
            
            const { data, oldData } = payload.payload || {};
            if (!data) return;

            // Only notify on status change
            if (oldData && data.is_up === oldData.is_up) return;

            const notification: RealtimeNotification = {
              id: `monitor-${data.id}-${Date.now()}`,
              type: 'service',
              eventType: 'UPDATE',
              title: data.name || 'Service',
              message: data.is_up
                ? `${data.name} is back online`
                : `${data.name} is down`,
              severity: data.is_up ? 'info' : 'critical',
              data: data,
              read: false,
              timestamp: new Date(),
              link: `/monitors/${data.id}`,
            };

            addNotification(notification);
          })
          // Note: postgres_changes removed - using API broadcast only to prevent duplicates
          .subscribe((status: string) => {
            console.log('🔌 Realtime subscription status:', status);
            setIsConnected(status === 'SUBSCRIBED');
          });

        // Save channel reference for broadcasting
        channelRef.current = channel;

        // Expose test function to window for debugging
        if (typeof window !== 'undefined') {
          (window as any).__testNotification = () => {
            const testNotif: RealtimeNotification = {
              id: `test-${Date.now()}`,
              type: 'incident',
              eventType: 'INSERT',
              title: '🧪 Test Notification',
              message: 'Real-time notifications are working!',
              severity: 'info',
              data: { id: 'test', title: 'Test' },
              read: false,
              timestamp: new Date(),
            };
            addNotification(testNotif);
            console.log('  Test notification added!');
          };
          console.log('💡 Test with: window.__testNotification()');
        }

        console.log('  Realtime notifications initialized for org:', currentOrg.id);
      } catch (error) {
        console.error('Failed to setup realtime notifications:', error);
        setIsConnected(false);
      }
    };

    setupRealtime();

    // Cleanup on unmount
    return () => {
      if (channel) {
        console.log('🔌 Unsubscribing from realtime notifications');
        channel.unsubscribe();
        channelRef.current = null;
      }
    };
  }, [user, session?.access_token, currentOrg?.id, addNotification]);

  const value: NotificationContextValue = {
    notifications,
    unreadCount,
    isConnected,
    markAsRead,
    markAllAsRead,
    clearNotification,
    clearAll,
    broadcastIncident,
    testNotification,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};

// Helper function to generate incident messages
function getIncidentMessage(eventType: string, incident: any): string {
  switch (eventType) {
    case 'INSERT':
      return `New ${incident.severity || 'medium'} severity incident: ${incident.title}`;
    case 'UPDATE':
      if (incident.status === 'resolved') {
        return `Incident resolved: ${incident.title}`;
      } else if (incident.status === 'acknowledged') {
        return `Incident acknowledged: ${incident.title}`;
      }
      return `Incident updated: ${incident.title}`;
    case 'DELETE':
      return `Incident deleted: ${incident.title}`;
    default:
      return incident.title || 'Incident event';
  }
}

export default NotificationProvider;
