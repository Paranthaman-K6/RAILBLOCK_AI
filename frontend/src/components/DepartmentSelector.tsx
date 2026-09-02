export default function DepartmentSelector({value, onChange}:{value:string, onChange:(v:string)=>void}){
  return <select aria-label="Select department" value={value} onChange={e=>onChange(e.target.value)}>
    <option>CONTROL_OFFICE</option><option>ENGINEERING</option><option>S_AND_T</option><option>TRACTION</option><option>PROJECTS</option><option>VIEWER</option>
  </select>
}
