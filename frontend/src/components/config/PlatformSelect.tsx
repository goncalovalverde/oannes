import React from 'react';
import clsx from 'clsx';

interface PlatformSelectProps {
  selected: string;
  onSelect: (platform: string) => void;
}

const PLATFORMS = [
  { id: 'jira',        label: 'Jira',         icon: '🔵', desc: 'Jira Cloud or Server' },
  { id: 'trello',      label: 'Trello',        icon: '🟦', desc: 'Boards & cards' },
  { id: 'azure_devops',label: 'Azure DevOps',  icon: '🔷', desc: 'Work items & boards' },
  { id: 'gitlab',      label: 'GitLab',        icon: '🟠', desc: 'Issues & milestones' },
  { id: 'linear',      label: 'Linear',        icon: '🟣', desc: 'Coming soon', disabled: true },
  { id: 'shortcut',    label: 'Shortcut',      icon: '🟢', desc: 'Coming soon', disabled: true },
  { id: 'csv',         label: 'CSV / Excel',   icon: '📄', desc: 'Import from file' },
];

export function PlatformSelect({ selected, onSelect }: PlatformSelectProps) {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-gray-900">Select your platform</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {PLATFORMS.map((p) => (
          <button
            key={p.id}
            onClick={() => onSelect(p.id)}
            disabled={p.disabled}
            className={clsx(
              'p-4 border rounded-lg text-left transition-all',
              selected === p.id
                ? 'border-blue-500 bg-blue-50 shadow-md'
                : 'border-gray-200 hover:border-gray-300 hover:shadow-sm',
              p.disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            <div className="text-2xl mb-2">{p.icon}</div>
            <div className="font-semibold text-gray-900">{p.label}</div>
            <div className="text-sm text-gray-600">{p.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
