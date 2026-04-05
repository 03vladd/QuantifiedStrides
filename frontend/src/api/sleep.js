import apiFetch from './client'

export const fetchSleepList   = (days) => apiFetch(`/api/v1/sleep?days=${days}`)
export const fetchSleepDetail = (id)   => apiFetch(`/api/v1/sleep/${id}`)
export const fetchSleepTrends = (days) => apiFetch(`/api/v1/sleep/trends?days=${days}`)
