import apiFetch from './client'

export const fetchRunningTrends    = (days)         => apiFetch(`/api/v1/running/trends?days=${days}`)
export const fetchBiomechanics     = (days)         => apiFetch(`/api/v1/running/biomechanics?days=${days}`)
export const fetchTerrainSummary   = (days, sport)  => apiFetch(`/api/v1/running/terrain?days=${days}&sport=${sport}`)
export const fetchWorkoutGAP       = (workoutId)    => apiFetch(`/api/v1/running/workouts/${workoutId}/gap`)
export const fetchElevDecoupling   = (workoutId)    => apiFetch(`/api/v1/running/workouts/${workoutId}/elevation-decoupling`)
