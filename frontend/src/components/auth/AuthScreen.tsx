import React, { useState } from 'react';
import { useAuthStore } from '../../stores/authStore.ts';

/* ------------------------------------------------------------------ */
/* Knovex Auth — Split-panel login / register screen                   */
/* Left: Brand manifesto + feature pills                               */
/* Right: Tabbed sign-in / register form                               */
/* ------------------------------------------------------------------ */

const FeaturePill: React.FC<{ label: string }> = ({ label }) => (
  <div className="inline-flex items-center space-x-1.5 border border-line bg-surface px-2.5 py-1 rounded-chip text-xs font-mono text-secondary">
    <span className="w-1.5 h-1.5 rounded-chip bg-mark" />
    <span>{label}</span>
  </div>
);

export const AuthScreen: React.FC = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgName, setOrgName] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<'admin' | 'user'>('admin');

  const { login, register, isLoading, error, clearError } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    if (isRegister) {
      if (!orgName.trim() || !email.trim() || password.length < 8) return;
      await register(orgName.trim(), email.trim(), password, fullName.trim() || undefined, role);
    } else {
      if (!email.trim() || !password) return;
      await login(email.trim(), password);
    }
  };

  const inputCls = 'w-full px-3 py-2 bg-surface border border-line text-ink text-sm rounded-input focus:border-mark focus:outline-none placeholder:text-muted transition-colors';
  const labelCls = 'block text-xs font-mono text-secondary mb-1 uppercase tracking-wider font-medium';

  return (
    <div className="w-full h-full flex flex-col md:flex-row bg-bg text-ink overflow-hidden">

      {/* ── Left: Brand manifesto ── */}
      <div className="w-full md:w-1/2 p-7 md:p-8 flex flex-col justify-between border-b md:border-b-0 md:border-r border-line bg-sidebar">
        <div>
          {/* Wordmark */}
          <div className="flex items-center space-x-2.5 mb-7">
            <img
              src="/logo.png"
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

      {/* ── Right: Auth form ── */}
      <div className="w-full md:w-1/2 p-7 md:p-8 flex items-center justify-center bg-bg">
        <div className="w-full max-w-sm">

          {/* Tab switcher */}
          <div className="flex border-b border-line mb-6">
            <button
              type="button"
              onClick={() => { setIsRegister(false); clearError(); }}
              className={`pb-3 text-sm font-sans font-medium mr-6 border-b-2 -mb-px transition-colors ${
                !isRegister
                  ? 'border-mark text-ink'
                  : 'border-transparent text-secondary hover:text-ink'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setIsRegister(true); clearError(); }}
              className={`pb-3 text-sm font-sans font-medium border-b-2 -mb-px transition-colors ${
                isRegister
                  ? 'border-mark text-ink'
                  : 'border-transparent text-secondary hover:text-ink'
              }`}
            >
              Create Organization
            </button>
          </div>

          {/* Error banner */}
          {error && (
            <div className="mb-4 px-3 py-2 border-l-2 border-danger text-danger text-xs font-sans bg-elevated/40 rounded-r-input">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <>
                <div>
                  <label className={labelCls}>Organization Name</label>
                  <input
                    type="text"
                    required
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="Acme Corp"
                    className={inputCls}
                  />
                </div>
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
                <div>
                  <label className={labelCls}>Account Role</label>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <button
                      type="button"
                      onClick={() => setRole('admin')}
                      className={`px-3 py-2 text-xs font-mono rounded-input border transition-all text-left cursor-pointer ${
                        role === 'admin'
                          ? 'border-mark bg-mark/10 text-ink font-semibold'
                          : 'border-line bg-surface text-secondary hover:text-ink'
                      }`}
                    >
                      <div className="font-bold text-ink mb-0.5">Admin</div>
                      <div className="text-[10px] text-muted">Upload & delete docs</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setRole('user')}
                      className={`px-3 py-2 text-xs font-mono rounded-input border transition-all text-left cursor-pointer ${
                        role === 'user'
                          ? 'border-mark bg-mark/10 text-ink font-semibold'
                          : 'border-line bg-surface text-secondary hover:text-ink'
                      }`}
                    >
                      <div className="font-bold text-ink mb-0.5">User</div>
                      <div className="text-[10px] text-muted">Chat & ask questions</div>
                    </button>
                  </div>
                </div>
              </>
            )}

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

            <div>
              <label className={labelCls}>Password {isRegister && '(min 8 chars)'}</label>
              <input
                type="password"
                required
                minLength={isRegister ? 8 : 6}
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
                : isRegister
                ? 'Create & Enter'
                : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
