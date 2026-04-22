import React, { useState } from 'react';
import clsx from 'clsx';

const STAGES = ['queue', 'start', 'in_flight', 'done'] as const;
const STAGE_LABELS: Record<string, string> = {
  queue: 'Queue',
  start: 'Start',
  in_flight: 'In Flight',
  done: 'Done',
};
const STAGE_DESCS: Record<string, string> = {
  queue: 'Not yet started',
  start: 'Cycle time begins here',
  in_flight: 'Active work stages',
  done: 'Cycle time ends here',
};

interface WorkflowConfigProps {
  statuses: string[];
  workflowMap: Record<string, string>;
  onWorkflowChange: (statusName: string, stage: string) => void;
}

export function WorkflowConfiguration({
  statuses,
  workflowMap,
  onWorkflowChange,
}: WorkflowConfigProps) {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Configure Workflow Stages</h2>
      <p className="text-gray-600">
        Drag statuses into the pipeline stages. The "Cycle time begins" and "Cycle time ends" stages define the start and end of the cycle time metric.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {STAGES.map((stage) => (
          <div
            key={stage}
            className="border-2 border-dashed border-gray-300 rounded-lg p-4 bg-gray-50 min-h-[200px]"
          >
            <div className="font-semibold text-gray-900 text-sm mb-2">
              {STAGE_LABELS[stage]}
            </div>
            <div className="text-xs text-gray-600 mb-4">{STAGE_DESCS[stage]}</div>

            <div className="space-y-2">
              {statuses
                .filter((s) => workflowMap[s] === stage)
                .map((status) => (
                  <div
                    key={status}
                    className="bg-white border border-gray-300 rounded p-2 text-sm cursor-move hover:shadow-md transition-shadow"
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer?.setData('status', status);
                    }}
                  >
                    {status}
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <h3 className="font-semibold text-gray-900">Unassigned Statuses</h3>
        <div className="flex flex-wrap gap-2">
          {statuses
            .filter((s) => !workflowMap[s])
            .map((status) => (
              <div
                key={status}
                className="bg-gray-100 border border-gray-300 rounded px-3 py-1 text-sm cursor-move hover:shadow-md transition-shadow"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer?.setData('status', status);
                }}
              >
                {status}
              </div>
            ))}
        </div>
      </div>

      {/* Drop zones for drag-and-drop */}
      {STAGES.map((stage) => (
        <div
          key={`drop-${stage}`}
          className="hidden"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const status = e.dataTransfer?.getData('status');
            if (status) {
              onWorkflowChange(status, stage);
            }
          }}
        />
      ))}
    </div>
  );
}
