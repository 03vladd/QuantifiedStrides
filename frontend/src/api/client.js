function getToken() {
  return localStorage.getItem('qs_token')
}

export function setToken(token) {
  localStorage.setItem('qs_token', token)
}

export function clearToken() {
  localStorage.removeItem('qs_token')
  localStorage.removeItem('qs_user')
}

async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(path, { ...options, headers })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

export default apiFetch
