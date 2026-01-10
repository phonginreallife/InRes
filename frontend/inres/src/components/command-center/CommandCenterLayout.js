'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import TopNav from './TopNav';
import SearchModal from './SearchModal';
import CreateIncidentModal from '../incidents/CreateIncidentModal';
import { useAuth } from '../../contexts/AuthContext';

export default function CommandCenterLayout({ children }) {
  const { isAuthenticated } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [showSearch, setShowSearch] = useState(false);
  const [showNewIncident, setShowNewIncident] = useState(false);

  // Pages that don't show the command center layout
  const isAuthPage = pathname === '/login' || pathname === '/signup';
  const isOnboardingPage = pathname === '/onboarding';
  const isLandingPage = pathname === '/';
  const isSharedPage = pathname.startsWith('/shared/');
  const showCommandCenter = isAuthenticated && !isAuthPage && !isOnboardingPage && !isLandingPage && !isSharedPage;

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // ⌘K or Ctrl+K for search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowSearch(true);
      }
      // Escape to close modals
      if (e.key === 'Escape') {
        setShowSearch(false);
        setShowNewIncident(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleOpenAI = () => {
    router.push('/ai-agent');
  };

  const handleIncidentCreated = (incident) => {
    setShowNewIncident(false);
    router.push(`/incidents/${incident.id}`);
  };

  if (!showCommandCenter) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Top Navigation */}
      <TopNav
        onNewIncident={() => setShowNewIncident(true)}
        onOpenSearch={() => setShowSearch(true)}
        onOpenAI={handleOpenAI}
      />

      {/* Main Content - with top padding for nav */}
      <main className="pt-14 min-h-screen">
        <div className="max-w-[1800px] mx-auto p-4 lg:p-6">
          {children}
        </div>
      </main>

      {/* Floating Action Bar (Mobile) */}
      <div className="fixed bottom-4 left-4 right-4 md:hidden z-40">
        <div className="bg-gray-900/95 backdrop-blur-xl border border-gray-800 rounded-2xl p-2 flex items-center justify-around shadow-2xl">
          <button
            onClick={() => setShowNewIncident(true)}
            className="flex flex-col items-center gap-1 p-2 text-red-400"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="text-[10px]">Incident</span>
          </button>
          <button
            onClick={() => setShowSearch(true)}
            className="flex flex-col items-center gap-1 p-2 text-gray-400"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="text-[10px]">Search</span>
          </button>
          <button
            onClick={handleOpenAI}
            className="flex flex-col items-center gap-1 p-2 text-cyan-400"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <span className="text-[10px]">AI</span>
          </button>
        </div>
      </div>

      {/* Search Modal */}
      <SearchModal isOpen={showSearch} onClose={() => setShowSearch(false)} />

      {/* New Incident Modal */}
      <CreateIncidentModal
        isOpen={showNewIncident}
        onClose={() => setShowNewIncident(false)}
        onIncidentCreated={handleIncidentCreated}
      />
    </div>
  );
}
