import React, { useEffect } from 'react';
import { useAuthStore } from './stores/authStore.ts';
import { useUIStore } from './stores/uiStore.ts';
import { AuthScreen } from './components/auth/AuthScreen.tsx';
import { AppLayout } from './components/layout/AppLayout.tsx';

export const App: React.FC = () => {
  const { user, isLoading, init } = useAuthStore();
  const { theme } = useUIStore();

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-bg text-ink font-mono text-xs">
        Loading Knovex…
      </div>
    );
  }

  if (!user) {
    return <AuthScreen />;
  }

  return <AppLayout />;
};
export default App;
