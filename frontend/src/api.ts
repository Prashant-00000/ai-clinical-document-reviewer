/**
 * API client — thin wrapper around fetch.
 * Reads VITE_API_URL from env (falls back to '' so dev proxy works).
 */
import type { ReportRow, ApiError } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errBody: Partial<ApiError> = {}
    try { errBody = await res.json() } catch { /* ignore */ }
    const msg = errBody?.error?.message ?? `HTTP ${res.status}`
    const err = new Error(msg) as Error & { code?: string; status?: number }
    err.code = errBody?.error?.code
    err.status = res.status
    throw err
  }
  return res.json() as Promise<T>
}

export async function analyzeText(text: string): Promise<ReportRow> {
  const form = new FormData()
  form.append('text', text)
  const res = await fetch(`${BASE}/api/analyze`, { method: 'POST', body: form })
  return handleResponse<ReportRow>(res)
}

export async function analyzeFile(file: File): Promise<ReportRow> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/api/analyze`, { method: 'POST', body: form })
  return handleResponse<ReportRow>(res)
}

export async function listReports(): Promise<ReportRow[]> {
  const res = await fetch(`${BASE}/api/reports`)
  return handleResponse<ReportRow[]>(res)
}

export async function getReport(id: string): Promise<ReportRow> {
  const res = await fetch(`${BASE}/api/reports/${id}`)
  return handleResponse<ReportRow>(res)
}

export async function deleteReport(id: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/api/reports/${id}`, { method: 'DELETE' })
  return handleResponse<{ message: string }>(res)
}
