import React from 'react';

interface AbstainedBlockProps {
  reason?: string;
}

export const AbstainedBlock: React.FC<AbstainedBlockProps> = ({ reason }) => {
  return (
    <div className="my-2 bg-hatched border border-line p-4 rounded-input">
      {/* Header row */}
      <div className="flex items-center space-x-2 mb-2">
        {/* Diagonal-striped swatch — pulls from the CSS hatched pattern */}
        <div className="w-3 h-3 bg-hatched border border-line rounded-chip shrink-0" />
        <span className="font-sans font-semibold text-sm text-ink">
          Nothing on file for this question
        </span>
      </div>

      {/* Reason text */}
      {reason && (
        <p className="font-sans text-xs text-secondary leading-relaxed ml-5">
          {reason}
        </p>
      )}

      {/* Hint */}
      <p className="font-mono text-xs text-muted mt-3 ml-5">
        Try uploading more documents or rephrasing the question.
      </p>
    </div>
  );
};
