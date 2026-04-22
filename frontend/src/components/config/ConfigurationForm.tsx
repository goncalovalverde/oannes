import React from 'react';

interface FieldDef {
  key: string;
  label: string;
  type?: string;
  placeholder?: string;
  help?: string;
  optional?: boolean;
  default?: string;
  options?: Array<{ value: string; label: string }>;
  conditional?: (config: Record<string, string>) => boolean;
}

interface ConfigurationFormProps {
  platform: string;
  config: Record<string, string>;
  fields: FieldDef[];
  onConfigChange: (key: string, value: string) => void;
  loading?: boolean;
}

export function ConfigurationForm({
  platform,
  config,
  fields,
  onConfigChange,
  loading
}: ConfigurationFormProps) {
  const visibleFields = fields.filter((f) => !f.conditional || f.conditional(config));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">{platform.toUpperCase()} Configuration</h2>
      
      {visibleFields.map((field) => (
        <div key={field.key} className="space-y-2">
          <label className="block font-medium text-gray-900">
            {field.label}
            {!field.optional && <span className="text-red-600 ml-1">*</span>}
          </label>

          {field.type === 'select' ? (
            <select
              value={config[field.key] ?? field.default ?? ''}
              onChange={(e) => onConfigChange(field.key, e.target.value)}
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select an option...</option>
              {field.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={field.type || 'text'}
              placeholder={field.placeholder}
              value={config[field.key] ?? ''}
              onChange={(e) => onConfigChange(field.key, e.target.value)}
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          )}

          {field.help && <p className="text-sm text-gray-600">{field.help}</p>}
        </div>
      ))}
    </div>
  );
}
