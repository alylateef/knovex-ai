import React, { useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore.ts';
import { useUIStore } from '../../stores/uiStore.ts';

/* ------------------------------------------------------------------ */
/* Knovex Auth — Enterprise Multi-Tenant Screen                        */
/* Left: Brand manifesto + feature pills                               */
/* Right: Tabbed sign-in / create org / join org form                  */
/* ------------------------------------------------------------------ */

const FeaturePill: React.FC<{ label: string }> = ({ label }) => (
  <div className="inline-flex items-center space-x-1.5 border border-line bg-surface px-2.5 py-1 rounded-chip text-xs font-mono text-secondary">
    <span className="w-1.5 h-1.5 rounded-chip bg-mark" />
    <span>{label}</span>
  </div>
);

type AuthMode = 'login' | 'create' | 'join';

export const AuthScreen: React.FC = () => {
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgName, setOrgName] = useState('');
  const [orgCode, setOrgCode] = useState('');
  const [fullName, setFullName] = useState('');

  const { login, register, join, isLoading, error, clearError } = useAuthStore();
  const { theme, toggleTheme } = useUIStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    if (mode === 'create') {
      if (!orgName.trim() || !email.trim() || password.length < 8) return;
      await register(orgName.trim(), email.trim(), password, fullName.trim() || undefined, 'admin');
    } else if (mode === 'join') {
      if (!orgCode.trim() || !email.trim() || password.length < 8) return;
      await join(orgCode.trim(), email.trim(), password, fullName.trim() || undefined, 'user');
    } else {
      if (!email.trim() || !password) return;
      await login(email.trim(), password);
    }
  };

  const inputCls = 'w-full px-3 py-2 bg-surface border border-line text-ink text-sm rounded-input focus:border-mark focus:outline-none placeholder:text-muted transition-colors';
  const labelCls = 'block text-xs font-mono text-secondary mb-1 uppercase tracking-wider font-medium';

  return (
    <div className="relative w-full h-full min-h-screen md:min-h-0 flex flex-col md:flex-row bg-bg text-ink overflow-y-auto md:overflow-hidden">

      {/* ── Theme toggle (Top Right) ── */}
      <div className="absolute top-4 right-4 z-20">
        <button
          type="button"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle Theme"
          className="p-1.5 text-secondary hover:text-ink hover:bg-elevated rounded-button border border-line bg-surface/80 backdrop-blur-xs transition-colors cursor-pointer shadow-xs"
        >
          {theme === 'dark' ? (
            <Sun size={15} strokeWidth={1.5} />
          ) : (
            <Moon size={15} strokeWidth={1.5} />
          )}
        </button>
      </div>

      {/* ── Left: Brand manifesto (Desktop only) ── */}
      <div className="hidden md:flex md:w-1/2 p-7 md:p-8 flex-col justify-between border-r border-line bg-sidebar shrink-0">
        <div>
          {/* Wordmark */}
          <div className="flex items-center space-x-2.5 mb-7">
            <img
              src="/logo.svg"
              alt="Knovex AI Logo"
              style={{ width: '28px', height: '28px' }}
              className="rounded-chip object-cover shrink-0"
            />
            <span className="font-sans font-bold text-lg text-ink tracking-tight">Knovex</span>
            <span className="font-mono text-xs text-muted border border-line px-1 rounded-chip">AI</span>
          </div>

          {/* Headline */}
          <h1 className="text-2xl font-sans font-bold text-ink mb-1 leading-tight">
            The Marked-Up&nbsp;Printout.
          </h1>
          <p className="text-xs font-mono text-muted uppercase tracking-wider mb-5">
            Document Intelligence Platform
          </p>

          <p className="text-sm font-sans text-secondary leading-relaxed max-w-sm mb-6">
            Enterprise-grade RAG with rigorous multi-tenant isolation, verified chunk grounding,
            and exact source attribution. Every claim is traceable. No hallucinated text passes unverified.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2">
            <FeaturePill label="Hybrid Retrieval" />
            <FeaturePill label="CrossEncoder Rerank" />
            <FeaturePill label="Evidence Grounding" />
            <FeaturePill label="Tenant Isolation" />
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 pt-5 border-t border-line text-xs font-mono text-muted">
          Qdrant · LangGraph · FastAPI · PostgreSQL
        </div>
      </div>

      {/* ── Right: Auth form (Mobile + Desktop) ── */}
      <div className="w-full md:w-1/2 p-4 sm:p-6 md:p-8 flex flex-col items-center justify-center bg-bg my-auto">
        <div className="w-full max-w-sm md:max-w-md bg-surface md:bg-transparent border border-line md:border-transparent rounded-xl md:rounded-none p-6 sm:p-7 md:p-0 shadow-sm md:shadow-none">

          {/* Mobile-only brand header */}
          <div className="md:hidden mb-6 select-none">
            <div className="flex items-center space-x-2.5 mb-2">
              <img
                src="/logo.svg"
                alt="Knovex AI Logo"
                style={{ width: '28px', height: '28px' }}
                className="rounded-chip object-cover shrink-0"
              />
              <span className="font-sans font-bold text-lg text-ink tracking-tight">Knovex</span>
              <span className="font-mono text-xs text-muted border border-line px-1 rounded-chip">AI</span>
            </div>
            <p className="text-xs font-mono text-secondary uppercase tracking-wider mb-3">
              Document Intelligence Platform
            </p>
            <div className="flex flex-wrap gap-1.5">
              <FeaturePill label="Hybrid RAG" />
              <FeaturePill label="CrossEncoder" />
              <FeaturePill label="Isolated Tenants" />
            </div>
          </div>

          {/* Tab switcher — 3 clean enterprise options */}
          <div className="flex border-b border-line mb-6">
            <button
              type="button"
              onClick={() => { setMode('login'); clearError(); }}
              className={`pb-3 text-sm font-sans font-medium mr-5 border-b-2 -mb-px transition-colors cursor-pointer ${
                mode === 'login'
                  ? 'border-mark text-ink'
                  : 'border-transparent text-secondary hover:text-ink'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setMode('create'); clearError(); }}
              className={`pb-3 text-sm font-sans font-medium mr-5 border-b-2 -mb-px transition-colors cursor-pointer ${
                mode === 'create'
                  ? 'border-mark text-ink'
                  : 'border-transparent text-secondary hover:text-ink'
              }`}
            >
              Create Org
            </button>
            <button
              type="button"
              onClick={() => { setMode('join'); clearError(); }}
              className={`pb-3 text-sm font-sans font-medium border-b-2 -mb-px transition-colors cursor-pointer ${
                mode === 'join'
                  ? 'border-mark text-ink'
                  : 'border-transparent text-secondary hover:text-ink'
              }`}
            >
              Join Org
            </button>
          </div>

          {/* Error banner */}
          {error && (
            <div className="mb-4 px-3 py-2 border-l-2 border-danger text-danger text-xs font-sans bg-elevated/40 rounded-r-input">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Mode 1: Create Organization */}
            {mode === 'create' && (
              <div>
                <label className={labelCls}>Organization Name</label>
                <input
                  type="text"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. FAST, AlyFirm, Acme"
                  className={inputCls}
                />
                <span className="block text-[11px] font-mono text-muted mt-1">
                  Creates a brand-new isolated workspace with a private Org Code.
                </span>
              </div>
            )}

            {/* Mode 2: Join Organization */}
            {mode === 'join' && (
              <div>
                <label className={labelCls}>Organization Code</label>
                <input
                  type="text"
                  required
                  value={orgCode}
                  onChange={(e) => setOrgCode(e.target.value)}
                  placeholder="e.g. FAST-9A2F"
                  className={inputCls}
                />
                <span className="block text-[11px] font-mono text-muted mt-1">
                  Ask your organization admin for your workspace code.
                </span>
              </div>
            )}

            {/* Optional full name for both create and join */}
            {(mode === 'create' || mode === 'join') && (
              <div>
                <label className={labelCls}>Full Name (Optional)</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                  className={inputCls}
                />
              </div>
            )}

            {/* Work Email */}
            <div>
              <label className={labelCls}>Work Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@enterprise.com"
                className={inputCls}
              />
            </div>

            {/* Password */}
            <div>
              <label className={labelCls}>Password {mode !== 'login' && '(min 8 chars)'}</label>
              <input
                type="password"
                required
                minLength={mode !== 'login' ? 8 : 6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={inputCls}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-mark hover:bg-mark-hover text-bg font-sans font-medium text-sm rounded-button transition-colors disabled:opacity-40 mt-3 cursor-pointer"
            >
              {isLoading
                ? 'Authenticating…'
                : mode === 'create'
                ? 'Create & Enter'
                : mode === 'join'
                ? 'Join Workspace'
                : 'Sign In'}
            </button>
          </form>

          {/* Mobile-only technical footer */}
          <div className="md:hidden mt-6 pt-4 border-t border-line text-[11px] font-mono text-muted text-center">
            Knovex AI · Enterprise Knowledge Architecture
          </div>
        </div>
      </div>
    </div>
  );
};
