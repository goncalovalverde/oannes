interface Props { lines?: number }

export default function LoadingSkeleton({ lines = 3 }: Props) {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-4 bg-surface2 rounded" style={{ width: `${100 - i * 10}%` }} />
      ))}
    </div>
  )
}

export function ChartSkeleton() {
  return (
    <div className="animate-pulse bg-surface2 rounded-xl h-48 w-full" />
  )
}
