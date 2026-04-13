import { useFilterStore } from '../../store/filterStore'
import { useItemTypes } from '../../api/hooks/useMetrics'

interface Props { title: string }

const WEEK_OPTIONS = [
  { label: 'Last 4 weeks',  value: 4 },
  { label: 'Last 12 weeks', value: 12 },
  { label: 'Last 6 months', value: 26 },
  { label: 'All time',      value: 520 },
]

const GRANULARITY_OPTIONS = [
  { label: 'Weekly',     value: 'week'   },
  { label: 'Bi-weekly',  value: 'biweek' },
  { label: 'Monthly',    value: 'month'  },
] as const

export default function Topbar({ title }: Props) {
  const { activeProjectId, weeks, itemType, granularity, setWeeks, setItemType, setGranularity } = useFilterStore()
  const { data: types = [] } = useItemTypes(activeProjectId)

  return (
    <div className="h-14 bg-surface border-b border-border px-6 flex items-center justify-between flex-shrink-0">
      <h1 className="text-[17px] font-bold">{title}</h1>
      <div className="flex items-center gap-2">
        <select
          value={weeks}
          onChange={e => setWeeks(Number(e.target.value))}
          className="bg-surface2 border border-border text-xs text-text rounded-full px-3 py-1.5 focus:outline-none focus:border-primary cursor-pointer"
        >
          {WEEK_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={granularity}
          onChange={e => setGranularity(e.target.value as 'week' | 'biweek' | 'month')}
          className="bg-surface2 border border-border text-xs text-text rounded-full px-3 py-1.5 focus:outline-none focus:border-primary cursor-pointer"
        >
          {GRANULARITY_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={itemType}
          onChange={e => setItemType(e.target.value)}
          className="bg-surface2 border border-border text-xs text-text rounded-full px-3 py-1.5 focus:outline-none focus:border-primary cursor-pointer"
        >
          <option value="all">All types</option>
          {types.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
    </div>
  )
}
