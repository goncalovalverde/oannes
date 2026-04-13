import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

const TITLES: Record<string, string> = {
  '/':            'Dashboard',
  '/throughput':  'Throughput',
  '/cycle-time':  'Cycle Time',
  '/lead-time':   'Lead Time',
  '/wip':         'Work in Progress',
  '/cfd':         'Cumulative Flow',
  '/aging-wip':   'Aging WIP',
  '/monte-carlo': 'Monte Carlo Forecast',
  '/raw-data':    'Raw Data',
  '/projects':    'Projects',
}

export default function AppShell() {
  const { pathname } = useLocation()
  const title = TITLES[pathname] ?? 'Oannes'

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Topbar title={title} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
