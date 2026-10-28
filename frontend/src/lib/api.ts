import type { components } from './api-schema'

export type GoalCreate = components['schemas']['GoalCreate']
export type Profile = components['schemas']['StudentPublic']
export type Curriculum = components['schemas']['CurriculumSnapshot']
export interface SavedGoal { goal_id: string; title: string; input_revision: number }

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message) }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const token = localStorage.getItem('learnnova.token')
  if (token) headers.set('X-Local-Token', token)
  let response: Response
  try { response = await fetch(`/api/v1${path}`, { ...options, headers }) }
  catch { throw new ApiError('NETWORK_ERROR', 'We couldn’t reach LearnNova. Check the local server and try again.', 0) }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(data.error?.code ?? 'REQUEST_FAILED', data.error?.message ?? 'Something went wrong. Please try again.', response.status)
  return data as T
}

export async function ensureProfile(displayName: string): Promise<Profile> {
  if (localStorage.getItem('learnnova.token')) return api<Profile>('/me')
  const profile = await api<components['schemas']['StudentCreated']>('/students', {
    method: 'POST', body: JSON.stringify({ display_name: displayName || null, timezone: 'Asia/Kolkata' }),
  })
  localStorage.setItem('learnnova.token', profile.client_token)
  return profile
}

export async function saveGoal(body: GoalCreate): Promise<SavedGoal> {
  const signature = JSON.stringify({ ...body, expected_revision: undefined })
  const pending = localStorage.getItem('learnnova.pending-goal')
  let intent: { signature: string; key: string; body: GoalCreate } | null = null
  if (pending) { try { intent = JSON.parse(pending) } catch { /* replace malformed local state */ } }
  if (!intent || intent.signature !== signature) {
    intent = { signature, key: crypto.randomUUID(), body }
    localStorage.setItem('learnnova.pending-goal', JSON.stringify(intent))
  }
  try {
    const result = await api<SavedGoal>('/goals', { method: 'POST', headers: { 'Idempotency-Key': intent.key }, body: JSON.stringify(intent.body) })
    localStorage.removeItem('learnnova.pending-goal')
    localStorage.setItem('learnnova.goal-id', result.goal_id)
    return result
  } catch (error) {
    if (error instanceof ApiError && error.code === 'STALE_REVISION') localStorage.removeItem('learnnova.pending-goal')
    throw error
  }
}
