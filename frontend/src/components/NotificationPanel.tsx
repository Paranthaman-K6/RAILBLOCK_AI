import { useEffect, useState } from 'react'
import api from '../services/api'

export interface NotificationItem {
  id: string
  message: string
  created_at: string
}

export default function NotificationPanel(){
  const [notes, setNotes]=useState<NotificationItem[]>([])
  const dept = localStorage.getItem('department')||'VIEWER'
  useEffect(()=>{
    api.get('/api/notifications', {params:{department:dept}}).then(r=>setNotes(r.data)).catch(()=>{})
  },[dept])
  return <div role="region" aria-label={`Notifications for ${dept}`} aria-live="polite">
    <h4>Notifications ({dept})</h4>
    {notes.length===0? <div>No notifications</div> : <ul>{notes.map((n:any)=><li key={n.id}>{n.message} - {new Date(n.created_at).toLocaleString()}</li>)}</ul>}
  </div>
}
