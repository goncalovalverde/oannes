import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import Dashboard from './pages/Dashboard'
import Throughput from './pages/Throughput'
import CycleTime from './pages/CycleTime'
import LeadTime from './pages/LeadTime'
import WIP from './pages/WIP'
import CFD from './pages/CFD'
import AgingWIP from './pages/AgingWIP'
import MonteCarlo from './pages/MonteCarlo'
import RawData from './pages/RawData'
import Projects from './pages/Projects'
import { ToastProvider } from './context/ToastContext'
import { ToastContainer } from './components/ui/ToastContainer'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/"            element={<Dashboard />} />
            <Route path="/throughput"  element={<Throughput />} />
            <Route path="/cycle-time"  element={<CycleTime />} />
            <Route path="/lead-time"   element={<LeadTime />} />
            <Route path="/wip"         element={<WIP />} />
            <Route path="/cfd"         element={<CFD />} />
            <Route path="/aging-wip"   element={<AgingWIP />} />
            <Route path="/monte-carlo" element={<MonteCarlo />} />
            <Route path="/raw-data"    element={<RawData />} />
            <Route path="/projects"    element={<Projects />} />
            <Route path="*"            element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <ToastContainer />
    </ToastProvider>
  )
}
