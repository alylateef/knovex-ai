import React, { useRef, useState } from 'react';
import { Upload, AlertCircle, X } from 'lucide-react';
import { useDocsStore } from '../../stores/docsStore.ts';

export const UploadDropzone: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { uploadDoc, isUploading, error } = useDocsStore();
  const [isDragging, setIsDragging] = useState(false);
  const [currentFileName, setCurrentFileName] = useState<string | null>(null);

  const handleFiles = async (files: FileList | File[]) => {
    const fileList = Array.from(files).filter(Boolean);
    if (fileList.length === 0) return;

    // Clear previous error
    useDocsStore.setState({ error: null });

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      const progressLabel = fileList.length > 1
        ? `Uploading (${i + 1}/${fileList.length}) ${file.name}…`
        : `Uploading ${file.name}…`;
      setCurrentFileName(progressLabel);

      try {
        await uploadDoc(file);
      } catch {
        // On error, docsStore records error; stop remaining batch so user can inspect error
        break;
      }
    }

    setCurrentFileName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleFiles(e.dataTransfer.files);
    }
  };

  const dismissError = (e: React.MouseEvent) => {
    e.stopPropagation();
    useDocsStore.setState({ error: null });
  };

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className={`
          border border-dashed rounded-input text-center transition-colors
          ${isDragging
            ? 'border-mark bg-mark-bg'
            : 'border-line hover:border-secondary bg-surface/40'
          }
        `}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
            e.target.blur();
          }}
          accept=".pdf,.txt,.md,.docx,.doc,.csv"
          multiple
          className="hidden"
          disabled={isUploading}
          tabIndex={-1}
        />
        <div
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.preventDefault();
            if (!isUploading) fileInputRef.current?.click();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              if (!isUploading) fileInputRef.current?.click();
            }
          }}
          className="cursor-pointer flex flex-col items-center justify-center py-3 px-2 select-none"
        >
          <Upload
            size={15}
            strokeWidth={1.5}
            className={`mb-1.5 transition-colors ${isDragging ? 'text-mark' : 'text-secondary'}`}
          />
          <span className={`text-xs font-sans font-medium transition-colors ${isDragging ? 'text-mark' : 'text-ink'} truncate max-w-full px-2`}>
            {isUploading ? (currentFileName || 'Uploading…') : 'Drop PDF, DOCX, CSV, or TXT'}
          </span>
          {!isUploading && (
            <span className="text-xs font-mono text-muted mt-0.5">
              or click to browse
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="p-2.5 rounded-input bg-danger/10 border border-danger/30 text-danger text-xs flex items-start gap-2 animate-fadeIn">
          <AlertCircle size={14} className="shrink-0 mt-0.5" />
          <span className="flex-1 break-words leading-tight">{error}</span>
          <button
            type="button"
            onClick={dismissError}
            className="text-danger/70 hover:text-danger shrink-0 p-0.5 cursor-pointer"
            title="Dismiss error"
          >
            <X size={12} strokeWidth={2} />
          </button>
        </div>
      )}
    </div>
  );
};
