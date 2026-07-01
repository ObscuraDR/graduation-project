import clsx from 'clsx'

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'blue' }) {
  const colorMap = {
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
    yellow: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    green: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    purple: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
    orange: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  }

  const valueColorMap = {
    blue: 'text-blue-400',
    red: 'text-red-400',
    yellow: 'text-amber-400',
    green: 'text-emerald-400',
    purple: 'text-violet-400',
    orange: 'text-orange-400',
  }

  return (
    <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5 hover:border-slate-700/60 transition-all duration-200">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{title}</p>
          <p className={clsx('text-2xl font-bold mt-1', valueColorMap[color] || 'text-slate-200')}>{value}</p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        {Icon && (
          <div className={clsx('p-3 rounded-xl border', colorMap[color] || colorMap.blue)}>
            <Icon className="w-6 h-6" />
          </div>
        )}
      </div>
    </div>
  )
}
