import apiFetch from './client'

export const fetchSportOptions  = ()                        => apiFetch('/api/v1/training/workouts/sports')
export const fetchWorkouts      = (days, sport)             => apiFetch(`/api/v1/training/workouts?days=${days}${sport && sport !== 'all' ? `&sport=${sport}` : ''}`)
export const fetchWorkout       = (id)                      => apiFetch(`/api/v1/training/workouts/${id}`)
export const fetchTrainingHistory = (today, days)           => apiFetch(`/api/v1/training/history?today=${today}&days=${days}`)
export const fetchHRVHistory    = (today, days)             => apiFetch(`/api/v1/training/hrv-history?today=${today}&days=${days}`)
