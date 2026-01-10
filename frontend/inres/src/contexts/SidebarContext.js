'use client';

import { createContext, useContext, useState, useEffect } from 'react';

const SidebarContext = createContext(undefined);

export function SidebarProvider({ children }) {
  const [collapsed, setCollapsed] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      
      if (mobile) {
        setCollapsed(true);
      } else {
        const saved = localStorage.getItem('sidebar-collapsed');
        if (saved !== null) {
          setCollapsed(JSON.parse(saved));
        } else {
          setCollapsed(false);
        }
      }
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handleSetCollapsed = (value) => {
    setCollapsed(value);
    if (!isMobile) {
      localStorage.setItem('sidebar-collapsed', JSON.stringify(value));
    }
  };

  return (
    <SidebarContext.Provider value={{ 
      collapsed, 
      setCollapsed: handleSetCollapsed, 
      isMobile 
    }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (context === undefined) {
    throw new Error('useSidebar must be used within a SidebarProvider');
  }
  return context;
}
