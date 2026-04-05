import apiFetch from './client'

export const fetchDashboard = (today) =>
  apiFetch(`/api/v1/dashboard${today ? `?today=${today}` : ''}`)
