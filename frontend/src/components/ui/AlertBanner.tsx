import clsx from 'clsx'

interface Props {
  type?: 'warning' | 'info' | 'error'
  children: React.ReactNode
  action?: { label: string; onClick: () => void }
}

const styles = {
  warning: 'bg-warning/8 border-warning/25 text-warning',
  info:    'bg-primary/8 border-primary/25 text-primary',
  error:   'bg-danger/8 border-danger/25 text-danger',
}

const icons = { warning: '⚠️', info: 'ℹ️', error: '🚨' }

export default function AlertBanner({ type = 'warning', children, action }: Props) {
  return (
    <div className={clsx('border rounded-lg px-4 py-3 flex items-center gap-3 text-sm mb-5', styles[type])}>
      <span>{icons[type]}</span>
      <span className="flex-1 text-text">{children}</span>
      {action && (
        <button onClick={action.onClick} className="underline text-sm" style={{ color: 'inherit' }}>
          {action.label} →
        </button>
      )}
    </div>
  )
}
