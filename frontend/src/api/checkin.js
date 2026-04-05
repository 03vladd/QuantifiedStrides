import apiFetch from './client'

export const fetchReadiness     = (date)    => apiFetch(`/api/v1/checkin/readiness/${date}`)
export const saveReadiness      = (payload) => apiFetch('/api/v1/checkin/readiness', { method: 'POST', body: JSON.stringify(payload) })
export const fetchReflection    = (date)    => apiFetch(`/api/v1/checkin/reflection/${date}`)
export const saveReflection     = (payload) => apiFetch('/api/v1/checkin/reflection', { method: 'POST', body: JSON.stringify(payload) })
export const fetchJournal       = (date)    => apiFetch(`/api/v1/checkin/journal/${date}`)
export const saveJournal        = (payload) => apiFetch('/api/v1/checkin/journal', { method: 'POST', body: JSON.stringify(payload) })
export const fetchJournalHistory = (days)   => apiFetch(`/api/v1/checkin/history?days=${days}`)
