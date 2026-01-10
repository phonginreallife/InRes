import "./globals.css";

import MobileNav from "../components/MobileNav";
import Sidebar from "../components/Sidebar";
import MainContent from "../components/MainContent";
import PWAInstallPrompt from "../components/PWAInstallPrompt";
import { AuthProvider } from "../contexts/AuthContext";
import { SidebarProvider } from "../contexts/SidebarContext";
import { OrgProvider } from "../contexts/OrgContext";
import { ThemeProvider } from "../contexts/ThemeContext";
import AuthWrapper from "../components/auth/AuthWrapper";
import { Toaster } from 'react-hot-toast';

export const metadata = {
  title: "InRes",
  description: "Enterprise-grade incident response & on-call platform powered by AI",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "InRes",
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: '/icon.svg',
    apple: [
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
  },
};

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  viewportFit: 'cover',
  themeColor: '#0066CC', // Primary Blue
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body 
        className="font-sans antialiased min-h-screen"
        style={{ background: 'var(--background)', color: 'var(--foreground)' }}
        suppressHydrationWarning
      >
        <ThemeProvider>
          <AuthProvider>
            <SidebarProvider>
              <OrgProvider>
                <AuthWrapper>
                {/* Desktop Sidebar */}
                <Sidebar />

                {/* Mobile Top Nav */}
                <MobileNav />

                {/* Main Content - margin adjusts based on sidebar state */}
                <MainContent>
                  {children}
                </MainContent>
              </AuthWrapper>
            </OrgProvider>
            <PWAInstallPrompt />
            <Toaster
              position="top-right"
              toastOptions={{
                duration: 4000,
                style: {
                  background: '#0d1b3e',
                  color: '#f1f5f9',
                  borderRadius: '12px',
                  border: '1px solid rgba(30, 58, 95, 0.5)',
                  boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)',
                },
                success: {
                  duration: 3000,
                  iconTheme: {
                    primary: '#4caf50',
                    secondary: '#fff',
                  },
                  style: {
                    borderLeft: '4px solid #4caf50',
                  },
                },
                error: {
                  duration: 5000,
                  iconTheme: {
                    primary: '#f44336',
                    secondary: '#fff',
                  },
                  style: {
                    borderLeft: '4px solid #f44336',
                  },
                },
                loading: {
                  iconTheme: {
                    primary: '#0066CC',
                    secondary: '#fff',
                  },
                  style: {
                    borderLeft: '4px solid #0066CC',
                  },
                },
              }}
            />
            </SidebarProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
