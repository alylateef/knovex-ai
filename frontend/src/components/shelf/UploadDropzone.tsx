import React, { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { useDocsStore } from '../../stores/docsStore.ts';

export const UploadDropzone: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { uploadDoc, isUploading } = useDocsStore();
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = (file: File) => {
    if (!file) return;
    uploadDoc(file).catch(() => {});
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  return (
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
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        accept=".pdf,.txt"
        className="sr-only"
        id="file-upload-input"
        disabled={isUploading}
      />
      <label
        htmlFor="file-upload-input"
        className="cursor-pointer flex flex-col items-center justify-center py-3 px-2"
      >
        <Upload
          size={15}
          strokeWidth={1.5}
          className={`mb-1.5 transition-colors ${isDragging ? 'text-mark' : 'text-secondary'}`}
        />
        <span className={`text-xs font-sans font-medium transition-colors ${isDragging ? 'text-mark' : 'text-ink'}`}>
          {isUploading ? 'Uploading…' : 'Drop PDF or TXT'}
        </span>
        {!isUploading && (
          <span className="text-xs font-mono text-muted mt-0.5">
            or click to browse
          </span>
        )}
      </label>
    </div>
  );
};
