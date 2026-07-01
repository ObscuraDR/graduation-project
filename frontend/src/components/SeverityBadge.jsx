import clsx from 'clsx'

const severityStyles = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
  high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  low: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
}

export default function SeverityBadge({ severity }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border',
        severityStyles[severity] || 'bg-slate-500/15 text-slate-400 border-slate-500/30'
      )}
    >
      {severity?.toUpperCase()}
    </span>
  )
}
