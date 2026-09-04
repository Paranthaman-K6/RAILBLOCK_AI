import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Layout from './components/Layout'
const Dashboard = lazy(()=>import('./pages/Dashboard'))
const DataImport = lazy(()=>import('./pages/DataImport'))
const TaskInbox = lazy(()=>import('./pages/TaskInbox'))
const Planner = lazy(()=>import('./pages/Planner'))
const DepartmentPlans = lazy(()=>import('./pages/DepartmentPlans'))
const Execution = lazy(()=>import('./pages/Execution'))
const Metrics = lazy(()=>import('./pages/Metrics'))
const Corridors = lazy(()=>import('./pages/Corridors'))
const Trains = lazy(()=>import('./pages/Trains'))
const Conflicts = lazy(()=>import('./pages/Conflicts'))
const Optimizer = lazy(()=>import('./pages/Optimizer'))
import NotFound from './pages/NotFound'

function Loader(){ return <div style={{padding:24, fontSize:13, color:'var(--text-muted)'}}>Loading…</div> }

export default function App(){
  return <BrowserRouter>
    <Layout>
      <Suspense fallback={<Loader/>}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/import" element={<DataImport />} />
          <Route path="/tasks" element={<TaskInbox />} />
          <Route path="/planner" element={<Planner />} />
          <Route path="/departments" element={<DepartmentPlans />} />
          <Route path="/execution" element={<Execution />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/corridors" element={<Corridors />} />
          <Route path="/trains" element={<Trains />} />
          <Route path="/conflicts" element={<Conflicts />} />
          <Route path="/optimizer" element={<Optimizer />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </Layout>
  </BrowserRouter>
}
