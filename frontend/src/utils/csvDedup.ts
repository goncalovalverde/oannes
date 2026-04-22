/**
 * CSV file deduplication utilities for the frontend.
 * 
 * Computes SHA256 hash of file content and compares against previous imports
 * to prevent accidental re-uploads of the same file.
 */

export async function computeCSVHash(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

export interface CSVFile {
  name: string;
  hash: string;
  size: number;
  lastModified: number;
}

// Store CSV import history in localStorage
const STORAGE_KEY = 'oannes_csv_history';

export function getCSVImportHistory(): CSVFile[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function saveCSVImportHistory(files: CSVFile[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(files));
  } catch (e) {
    console.warn('Failed to save CSV import history:', e);
  }
}

export function checkIfCSVWasImported(file: File, hash: string): CSVFile | null {
  const history = getCSVImportHistory();
  return history.find(f => f.hash === hash && f.name === file.name) || null;
}

export function recordCSVImport(file: File, hash: string) {
  const history = getCSVImportHistory();
  const existing = history.findIndex(f => f.hash === hash && f.name === file.name);
  
  const record: CSVFile = {
    name: file.name,
    hash,
    size: file.size,
    lastModified: file.lastModified,
  };
  
  if (existing >= 0) {
    history[existing] = record;
  } else {
    history.push(record);
  }
  
  saveCSVImportHistory(history.slice(-20)); // Keep only last 20 imports
}
