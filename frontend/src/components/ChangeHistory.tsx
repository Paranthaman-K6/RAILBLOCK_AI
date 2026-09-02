export default function ChangeHistory({history}:{history:any}){
  if(!history) return null
  return <div>
    <h4>History</h4>
    <pre style={{background:'#f5f5f5', padding:8, overflow:'auto'}}>{JSON.stringify(history, null, 2)}</pre>
  </div>
}
