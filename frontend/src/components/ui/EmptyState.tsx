interface Props {
  icon?: string
  title: string
  description: string
  action?: { label: string; onClick: () => void }
}

export default function EmptyState({ icon = '📊', title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-5xl mb-4">{icon}</div>
      <div className="text-lg font-semibold text-text mb-2">{title}</div>
      <div className="text-sm text-muted2 max-w-xs mb-6">{description}</div>
      {action && (
        <button
          onClick={action.onClick}
          className="bg-primary hover:bg-primary/90 text-white rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
