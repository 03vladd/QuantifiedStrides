import apiFetch from './client'

export const triggerSync = () =>
  apiFetch('/api/v1/sync', { method: 'POST' })
