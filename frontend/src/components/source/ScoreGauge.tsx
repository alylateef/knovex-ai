import React from 'react';

interface ScoreGaugeProps {
  label: string;
  value?: number;
}

export const ScoreGauge: React.FC<ScoreGaugeProps> = ({ label, value }) => {
  const normalized = typeof value === 'number' ? Math.max(0, Math.min(1, value)) : null;
  const pct = normalized !== null ? normalized * 100 : 0;

  // Color the gauge based on score threshold
  const barColor =
    normalized === null
      ? ''
      : normalized >= 0.7
      ? 'bg-mark'
      : normalized >= 0.4
      ? 'bg-mark opacity-60'
      : 'bg-secondary opacity-40';

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs font-mono text-secondary">
        <span>{label}</span>
        <span className={normalized !== null && normalized >= 0.7 ? 'text-mark font-medium' : ''}>
          {normalized !== null ? normalized.toFixed(3) : '—'}
        </span>
      </div>
      <div className="w-full h-1 bg-elevated overflow-hidden rounded-chip">
        {normalized !== null && (
          <div
            style={{ width: `${pct}%` }}
            className={`h-full transition-all ${barColor}`}
          />
        )}
      </div>
    </div>
  );
};
