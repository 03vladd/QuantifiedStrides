import apiFetch from './client'

export const fetchGarminWorkouts   = (days = 90)         => apiFetch(`/api/v1/strength/workouts?days=${days}`)
export const fetchSessions         = (days = 90)         => apiFetch(`/api/v1/strength/sessions?days=${days}`)
export const fetchSession          = (id)                 => apiFetch(`/api/v1/strength/sessions/${id}`)
export const fetch1RMHistory       = (exercise, days)     => apiFetch(`/api/v1/strength/1rm?exercise=${encodeURIComponent(exercise)}&days=${days}`)
export const fetchTrackedExercises = ()                   => apiFetch('/api/v1/strength/1rm/exercises')
export const fetchExerciseNames    = ()                   => apiFetch('/api/v1/strength/exercises').then(list => list.map(e => e.name))
export const createSession         = (payload)            => apiFetch('/api/v1/strength/sessions', { method: 'POST', body: JSON.stringify(payload) })
