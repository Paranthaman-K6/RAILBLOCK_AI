export const DEPARTMENTS = [
  'CONTROL_OFFICE',
  'ENGINEERING',
  'S_AND_T',
  'TRACTION',
  'PROJECTS',
  'VIEWER',
  'ADMIN',
] as const

export type Department = typeof DEPARTMENTS[number]

export const DEPARTMENT_LABELS: Record<string, string> = {
  CONTROL_OFFICE: 'Control Office',
  ENGINEERING: 'Engineering',
  S_AND_T: 'S&T',
  TRACTION: 'Traction',
  PROJECTS: 'Projects',
  VIEWER: 'Viewer',
  ADMIN: 'Admin',
}

export const APPROVER_ROLES = [
  'ENGINEERING',
  'S_AND_T',
  'TRACTION',
  'PROJECTS',
  'CONTROL_OFFICE',
  'ADMIN',
] as const
