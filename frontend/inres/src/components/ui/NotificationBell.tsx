'use client';

import { useState, useRef, useEffect } from 'react';
import { useNotifications, RealtimeNotification } from '../../contexts/NotificationContext';
import Link from 'next/link';

interface NotificationBellProps {
  collapsed?: boolean;
}

export default function NotificationBell({ collapsed = false }: NotificationBellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [popupNotification, setPopupNotification] = useState<RealtimeNotification | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const lastNotificationIdRef = useRef<string | null>(null);
  const {
    notifications,
    unreadCount,
    isConnected,
    markAsRead,
    markAllAsRead,
    clearNotification,
    clearAll,
  } = useNotifications();

  // Show popup when new notification arrives
  useEffect(() => {
    if (notifications.length > 0) {
      const latest = notifications[0];
      if (latest.id !== lastNotificationIdRef.current) {
        lastNotificationIdRef.current = latest.id;
        setPopupNotification(latest);
        
        // Auto-hide popup after 5 seconds
        const timer = setTimeout(() => {
          setPopupNotification(null);
        }, 5000);
        
        return () => clearTimeout(timer);
      }
    }
  }, [notifications]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Format relative time
  const formatTime = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Popup Notification - appears above bell like a message */}
      {popupNotification && !isOpen && (
        <div 
          className="absolute bottom-full right-0 mb-3 w-80 animate-fade-in cursor-pointer z-50"
          onClick={() => {
            setPopupNotification(null);
            if (popupNotification.link) {
              window.location.href = popupNotification.link;
            }
          }}
        >
          <div className={`relative px-4 py-3 rounded-xl shadow-2xl border backdrop-blur-sm ${
            popupNotification.type === 'incident' 
              ? 'bg-navy-800 border-red-500/50'
              : popupNotification.type === 'alert'
              ? 'bg-navy-800 border-orange-500/50'
              : 'bg-navy-800 border-green-500/50'
          }`}>
            <p className={`text-sm font-semibold ${
              popupNotification.type === 'incident' 
                ? 'text-red-400'
                : popupNotification.type === 'alert'
                ? 'text-orange-400'
                : 'text-green-400'
            }`}>{popupNotification.title}</p>
            <p className="text-xs text-gray-300 mt-1">{popupNotification.message}</p>
            <p className="text-[10px] text-gray-500 mt-1.5">Click to view • Auto-hides in 5s</p>
            {/* Arrow pointing to bell */}
            <div className={`absolute -bottom-2 right-4 w-3 h-3 rotate-45 bg-navy-800 ${
              popupNotification.type === 'incident' 
                ? 'border-r border-b border-red-500/50'
                : popupNotification.type === 'alert'
                ? 'border-r border-b border-orange-500/50'
                : 'border-r border-b border-green-500/50'
            }`} />
          </div>
        </div>
      )}

      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`relative p-2 rounded-lg transition-all duration-200 ${
          isOpen
            ? 'bg-primary-500/20 text-primary-400'
            : 'text-gray-400 hover:text-white hover:bg-navy-700/50'
        }`}
        title={collapsed ? `Notifications${unreadCount > 0 ? ` (${unreadCount})` : ''}` : undefined}
      >
        {/* Bell Icon */}
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* Unread Badge */}
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] flex items-center justify-center px-1 text-[10px] font-bold text-white bg-red-500 rounded-full animate-pulse">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}

        {/* Status Indicator - Red when unread, Green when connected, Gray when disconnected */}
        <span
          className={`absolute bottom-0 right-0 w-2 h-2 rounded-full border border-navy-800 ${
            unreadCount > 0 
              ? 'bg-red-500 animate-pulse' 
              : isConnected 
                ? 'bg-green-500' 
                : 'bg-gray-500'
          }`}
          title={unreadCount > 0 ? `${unreadCount} unread` : isConnected ? 'Real-time connected' : 'Connecting...'}
        />
      </button>

      {/* Dropdown Panel - Opens upward from bottom-right */}
      {isOpen && (
        <div className="absolute right-0 bottom-full mb-2 w-96 max-h-[480px] bg-navy-800 border border-navy-600/50 rounded-xl shadow-2xl overflow-hidden z-50 animate-fade-in">
          {/* Header */}
          <div className="px-4 py-3 border-b border-navy-700/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-white">Notifications</h3>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-primary-500/20 text-primary-400">
                  {unreadCount} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {notifications.length > 0 && (
                <>
                  <button
                    onClick={markAllAsRead}
                    className="text-xs text-gray-400 hover:text-white transition-colors"
                  >
                    Mark all read
                  </button>
                  <span className="text-gray-600">•</span>
                  <button
                    onClick={clearAll}
                    className="text-xs text-gray-400 hover:text-red-400 transition-colors"
                  >
                    Clear all
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Notifications List */}
          <div className="max-h-[380px] overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-12 text-center">
                <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-navy-700/50 flex items-center justify-center">
                  <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                </div>
                <p className="text-sm text-gray-400">No notifications yet</p>
                <p className="text-xs text-gray-500 mt-1">
                  {isConnected ? 'Listening for real-time events...' : 'Connecting to real-time...'}
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-navy-700/30">
                {notifications.map((notification) => (
                  <li
                    key={notification.id}
                    className={`group relative ${
                      notification.read ? 'bg-transparent' : 'bg-primary-500/5'
                    }`}
                  >
                    {notification.link ? (
                      <Link
                        href={notification.link}
                        onClick={() => {
                          markAsRead(notification.id);
                          setIsOpen(false);
                        }}
                        className="block px-4 py-3 hover:bg-navy-700/30 transition-colors"
                      >
                        <NotificationContent
                          notification={notification}
                          formatTime={formatTime}
                        />
                      </Link>
                    ) : (
                      <div
                        className="px-4 py-3 hover:bg-navy-700/30 transition-colors cursor-pointer"
                        onClick={() => markAsRead(notification.id)}
                      >
                        <NotificationContent
                          notification={notification}
                          formatTime={formatTime}
                        />
                      </div>
                    )}

                    {/* Delete button */}
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        clearNotification(notification.id);
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>

                    {/* Unread indicator */}
                    {!notification.read && (
                      <div className="absolute left-1 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-primary-500" />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-navy-700/50 bg-navy-900/50">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-500'}`} />
                {isConnected ? 'Real-time connected' : 'Connecting...'}
              </span>
              <Link
                href="/profile?tab=notifications"
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                Settings
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Extracted notification content component
function NotificationContent({
  notification,
  formatTime,
}: {
  notification: RealtimeNotification;
  formatTime: (d: Date) => string;
}) {
  return (
    <div className="flex items-start gap-3 pr-6">
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium truncate ${notification.read ? 'text-gray-300' : 'text-white'}`}>
          {notification.title}
        </p>
        <p className="text-xs text-gray-400 line-clamp-2 mt-0.5">
          {notification.message}
        </p>
        <p className="text-[10px] text-gray-500 mt-1">
          {formatTime(notification.timestamp)}
        </p>
      </div>
    </div>
  );
}
