'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

const QUICK_ACTIONS = [
  { id: 'new-incident', label: 'Create new incident', icon: '🔥', action: '/incidents/new' },
  { id: 'ai-agent', label: 'Open AI Assistant', icon: '🤖', action: '/ai-agent' },
  { id: 'view-services', label: 'View all services', icon: '✅', action: '/monitors' },
  { id: 'manage-teams', label: 'Manage teams', icon: '👥', action: '/groups' },
  { id: 'settings', label: 'Settings', icon: '⚙️', action: '/profile' },
];

const RECENT_ITEMS = [
  { id: '1', type: 'incident', label: 'High CPU on prod-api-01', href: '/incidents/1' },
  { id: '2', type: 'service', label: 'API Gateway', href: '/monitors/1' },
  { id: '3', type: 'incident', label: 'Database connection pool', href: '/incidents/2' },
];

export default function SearchModal({ isOpen, onClose }) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const router = useRouter();

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const filteredActions = query
    ? QUICK_ACTIONS.filter(a => a.label.toLowerCase().includes(query.toLowerCase()))
    : QUICK_ACTIONS;

  const filteredRecent = query
    ? RECENT_ITEMS.filter(r => r.label.toLowerCase().includes(query.toLowerCase()))
    : RECENT_ITEMS;

  const allItems = [...filteredActions, ...filteredRecent];

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, allItems.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = allItems[selectedIndex];
      if (item) {
        router.push(item.action || item.href);
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-x-4 top-[15vh] md:inset-x-auto md:left-1/2 md:-translate-x-1/2 md:w-full md:max-w-xl z-50">
        <div className="bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden">
          {/* Search Input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800">
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search incidents, services, or type a command..."
              className="flex-1 bg-transparent text-white placeholder-gray-500 focus:outline-none"
            />
            <kbd className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">ESC</kbd>
          </div>

          {/* Results */}
          <div className="max-h-[60vh] overflow-y-auto">
            {/* Quick Actions */}
            {filteredActions.length > 0 && (
              <div className="p-2">
                <p className="px-2 py-1 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Quick Actions
                </p>
                {filteredActions.map((action, index) => (
                  <button
                    key={action.id}
                    onClick={() => {
                      router.push(action.action);
                      onClose();
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                      selectedIndex === index
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-gray-300 hover:bg-gray-800/50'
                    }`}
                  >
                    <span className="text-lg">{action.icon}</span>
                    <span className="text-sm">{action.label}</span>
                    {selectedIndex === index && (
                      <span className="ml-auto text-xs text-gray-500">↵ Enter</span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Recent Items */}
            {filteredRecent.length > 0 && (
              <div className="p-2 border-t border-gray-800">
                <p className="px-2 py-1 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Recent
                </p>
                {filteredRecent.map((item, index) => {
                  const itemIndex = filteredActions.length + index;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        router.push(item.href);
                        onClose();
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                        selectedIndex === itemIndex
                          ? 'bg-blue-500/20 text-blue-400'
                          : 'text-gray-300 hover:bg-gray-800/50'
                      }`}
                    >
                      <span className="text-lg">
                        {item.type === 'incident' ? '🔥' : '✅'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{item.label}</p>
                        <p className="text-xs text-gray-500 capitalize">{item.type}</p>
                      </div>
                      {selectedIndex === itemIndex && (
                        <span className="text-xs text-gray-500">↵ Enter</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {/* No Results */}
            {query && filteredActions.length === 0 && filteredRecent.length === 0 && (
              <div className="p-8 text-center text-gray-500">
                <p>No results found for &quot;{query}&quot;</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-gray-800 flex items-center justify-between text-xs text-gray-500">
            <div className="flex items-center gap-3">
              <span>↑↓ Navigate</span>
              <span>↵ Select</span>
            </div>
            <span>⌘K to open</span>
          </div>
        </div>
      </div>
    </>
  );
}
