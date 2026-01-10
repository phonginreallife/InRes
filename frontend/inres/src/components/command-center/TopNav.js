'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';

export default function TopNav({ onNewIncident, onOpenSearch, onOpenAI }) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const pathname = usePathname();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const navItems = [
    { href: '/dashboard', label: 'Dashboard', icon: '📊' },
    { href: '/incidents', label: 'Incidents', icon: '🔥' },
    { href: '/monitors', label: 'Services', icon: '✅' },
    { href: '/groups', label: 'Teams', icon: '👥' },
    { href: '/alerts', label: 'Alerts', icon: '🔔' },
  ];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-14 bg-gray-900/95 dark:bg-gray-950/95 backdrop-blur-xl border-b border-gray-800/50">
      <div className="h-full max-w-[1800px] mx-auto px-4 flex items-center justify-between">
        {/* Left: Logo + Nav */}
        <div className="flex items-center gap-6">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-2 group">
            <div className="relative">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 group-hover:shadow-blue-500/40 transition-shadow">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </div>
            <span className="text-lg font-bold text-white hidden sm:block">InRes</span>
          </Link>

          {/* Nav Items */}
          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  pathname === item.href || pathname.startsWith(item.href + '/')
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                }`}
              >
                <span className="mr-1.5">{item.icon}</span>
                {item.label}
              </Link>
            ))}
          </div>
        </div>

        {/* Center: Search */}
        <button
          onClick={onOpenSearch}
          className="hidden sm:flex items-center gap-2 px-4 py-1.5 bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 rounded-lg text-gray-400 hover:text-white transition-all min-w-[200px] lg:min-w-[300px]"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span className="text-sm">Search...</span>
          <kbd className="ml-auto text-xs bg-gray-700/50 px-1.5 py-0.5 rounded">⌘K</kbd>
        </button>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {/* New Incident Button */}
          <button
            onClick={onNewIncident}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600 rounded-lg text-white text-sm font-medium shadow-lg shadow-red-500/20 hover:shadow-red-500/40 transition-all"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="hidden lg:inline">New Incident</span>
          </button>

          {/* AI Agent */}
          <button
            onClick={onOpenAI}
            className="p-2 rounded-lg text-cyan-400 hover:bg-cyan-500/10 hover:text-cyan-300 transition-all"
            title="AI Assistant"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </button>

          {/* Notifications */}
          <button className="relative p-2 rounded-lg text-gray-400 hover:bg-gray-800/50 hover:text-white transition-all">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg text-gray-400 hover:bg-gray-800/50 hover:text-white transition-all"
          >
            {theme === 'dark' ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>

          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-800/50 transition-all"
            >
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-white text-xs font-medium">
                {user?.email?.[0]?.toUpperCase() || 'U'}
              </div>
            </button>

            {showUserMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                <div className="absolute right-0 top-full mt-2 w-48 bg-gray-900 border border-gray-800 rounded-lg shadow-xl z-50 py-1">
                  <div className="px-3 py-2 border-b border-gray-800">
                    <p className="text-sm font-medium text-white truncate">{user?.email}</p>
                    <p className="text-xs text-gray-500">On-call now</p>
                  </div>
                  <Link href="/profile" className="block px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800/50">
                    Profile Settings
                  </Link>
                  <Link href="/agent-config" className="block px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800/50">
                    Integrations
                  </Link>
                  <button
                    onClick={logout}
                    className="w-full text-left px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-gray-800/50"
                  >
                    Sign Out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
