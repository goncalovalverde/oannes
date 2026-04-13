import clsx from 'clsx'

interface Props {
  label: string
  value: string | number
  sub?: string
  trend?: { label: string; positive: boolean }
  accentColor?: string
  children?: React.ReactNode
}

export default function KpiCard({ label, value, sub, trend, accentColor = '#6366f1', children }: Props) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 relative overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-[3px] rounded-t-xl" style={{ background: accentColor }} />
      <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-2">{label}</div>
      <div className="text-3xl font-extrabold tracking-tight leading-none" style={{ color: '#e2e8f0' }}>{value}</div>
      {sub && <div className="text-xs text-muted2 mt-1">{sub}</div>}
      {trend && (
        <div className={clsx('text-xs mt-1 font-medium', trend.positive ? 'text-success' : 'text-danger')}>
          {trend.label}
        </div>
      )}
      {children && <div className="mt-3">{children}</div>}
    </div>
  )
}
