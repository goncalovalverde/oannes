import React, { useState, useRef, useCallback } from 'react';
import { computeCSVHash, checkIfCSVWasImported, recordCSVImport } from '../../utils/csvDedup';
import { useToast } from '../../context/ToastContext';

interface CSVUploadProps {
  onFileSelected: (file: File) => void;
  isValidating?: boolean;
  selectedFile?: File | null;
}

export function CSVUpload({ onFileSelected, isValidating, selectedFile }: CSVUploadProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();
  const [isDuplicate, setIsDuplicate] = useState(false);

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      // Compute hash and check for duplicates
      const hash = await computeCSVHash(file);
      const duplicate = checkIfCSVWasImported(file, hash);

      if (duplicate) {
        setIsDuplicate(true);
        showToast(`Warning: This file was imported before (${new Date(duplicate.lastModified).toLocaleDateString()}). Are you sure you want to re-import?`, 'warning', 5000);
      } else {
        setIsDuplicate(false);
      }

      onFileSelected(file);
    } catch (error) {
      console.error('Failed to compute file hash:', error);
      showToast('Failed to validate file. Please try again.', 'error', 3000);
    }
  }, [onFileSelected, showToast]);

  return (
    <div className="space-y-4">
      <div>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={isValidating}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isValidating ? '🔄 Validating...' : selectedFile ? '📄 Change file...' : '📂 Select CSV/Excel file'}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>

      {selectedFile && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
          <p className="text-sm font-medium text-blue-900">📄 {selectedFile.name}</p>
          <p className="text-xs text-blue-700 mt-1">
            Size: {(selectedFile.size / 1024).toFixed(2)} KB
          </p>
          {isDuplicate && (
            <p className="text-xs text-yellow-700 mt-2 font-medium">
              ⚠️ This file was imported before. Proceed with caution to avoid duplicates.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
