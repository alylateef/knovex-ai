import React from 'react';

interface AbstainedBlockProps {
  reason?: string;
}

export const AbstainedBlock: React.FC<AbstainedBlockProps> = ({ reason }) => {
  return (
    <div className="my-3 bg-surface border border-line p-4 rounded-button shadow-sm">
      {/* Header row */}
      <div className="flex items-center space-x-2 mb-2">
        <span className="w-2 h-2 rounded-full bg-secondary shrink-0" />
        <span className="font-sans font-semibold text-sm text-ink">
          Nothing on file for this question
        </span>
      </div>

      {/* Reason text */}
      {reason && (
        <p className="font-sans text-xs text-secondary leading-relaxed ml-4">
          {reason}
        </p>
      )}

      {/* Hint */}
      <p className="font-mono text-xs text-muted mt-2 ml-4">
        Try asking about the content of your uploaded documents or upload relevant files.
      </p>
    </div>
  );
};
