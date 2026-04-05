import apiFetch from './client'

export const login    = (body) => apiFetch('/api/v1/auth/login',    { method: 'POST',   body: JSON.stringify(body) })
export const register = (body) => apiFetch('/api/v1/auth/register', { method: 'POST',   body: JSON.stringify(body) })
export const getMe    = ()     => apiFetch('/api/v1/auth/me')
export const updateMe = (body) => apiFetch('/api/v1/auth/me',       { method: 'PUT',    body: JSON.stringify(body) })
export const deleteMe = ()     => fetch('/api/v1/auth/me',          { method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('qs_token')}` } })
