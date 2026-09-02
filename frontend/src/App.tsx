import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import DataImport from './pages/DataImport'
import TaskInbox from './pages/TaskInbox'
import Planner from './pages/Planner'
import DepartmentPlans from './pages/DepartmentPlans'
import Execution from './pages/Execution'
import Metrics from './pages/Metrics'
import Corridors from './pages/Corridors'
import Trains from './pages/Trains'
import Conflicts from './pages/Conflicts'
import Optimizer from './pages/Optimizer'
import NotFound from './pages/NotFound'

export default function App(){
  return <BrowserRouter>
    <Layout>
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
    </Layout>
  </BrowserRouter>
}
