import React from 'react';
import { useToast, type ToastType } from '../../context/ToastContext';

const typeStyles: Record<ToastType, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
};

const typeIcons: Record<ToastType, string> = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
};

interface ToastItemProps {
  id: string;
  message: string;
  type: ToastType;
  onDismiss: (id: string) => void;
}

function ToastItem({ id, message, type, onDismiss }: ToastItemProps) {
  return (
    <div
      className={`flex items-center justify-between gap-3 p-4 border rounded-lg shadow-md animate-slide-in ${typeStyles[type]}`}
      role="alert"
    >
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold">{typeIcons[type]}</span>
        <p className="text-sm">{message}</p>
      </div>
      <button
        onClick={() => onDismiss(id)}
        className="text-sm opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

export function ToastContainer() {
  const { toasts, dismissToast } = useToast();

  return (
    <div
      className="fixed bottom-4 right-4 flex flex-col gap-3 max-w-md z-50"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          id={toast.id}
          message={toast.message}
          type={toast.type}
          onDismiss={dismissToast}
        />
      ))}
    </div>
  );
}
