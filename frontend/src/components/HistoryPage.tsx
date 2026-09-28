import { useEffect, useState, useCallback } from 'react'
import { FileText, Trash2, ChevronRight, RefreshCw, AlertCircle, Loader2 } from 'lucide-react'
import { listReports, deleteReport, getReport } from '../api'
import type { ReportRow } from '../types'
import ReportView from './ReportView'

const PAGE_SIZE = 20

function statusBadge(status: ReportRow['status']) {
  if (status === 'completed') return <span className="badge-success">Completed</span>
  if (status === 'completed_with_warnings') return <span className="badge-warning">Warnings</span>
  if (status === 'no_clinical_content') return <span className="badge-muted">No clinical content</span>
  if (status === 'failed') return <span className="badge-danger">Failed</span>
  return <span className="badge-muted">Processing</span>
}

function inputDetails(type: ReportRow['input_type']) {
  if (type === 'pdf') return { label: 'PDF', icon: '📄' }
  if (type === 'image') return { label: 'Image', icon: '🖼️' }
  return { label: 'Text', icon: '📝' }
}

export default function HistoryPage() {
  const [reports, setReports] = useState<ReportRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<ReportRow | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listReports()
      setReports(data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()))
      setVisibleCount(PAGE_SIZE)
    } catch (e: unknown) {
      setError((e as Error).message || 'Failed to load history.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openReport = async (row: ReportRow) => {
    try {
      const full = await getReport(row.id)
      setSelected(full)
    } catch { setSelected(row) }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm('Delete this report? This cannot be undone.')) return
    setDeleting(id)
    try {
      await deleteReport(id)
      setReports(prev => prev.filter(r => r.id !== id))
      if (selected?.id === id) setSelected(null)
    } catch { /* ignore */ }
    finally { setDeleting(null) }
  }

  const visibleReports = reports.slice(0, visibleCount)

  if (loading) return (
    <div className="flex items-center justify-center" style={{ minHeight: 300, gap: 12, color: '#6b7280' }}>
      <div className="spinner" style={{ borderTopColor: '#3b82f6' }} />
      Loading history…
    </div>
  )

  if (error) return (
    <div className="critical-alert flex items-center gap-3" style={{ maxWidth: 600, margin: '40px auto' }}>
      <AlertCircle size={20} color="#ef4444" />
      <span style={{ color: '#fca5a5' }}>{error}</span>
    </div>
  )

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 style={{ fontWeight: 800, fontSize: '1.5rem', margin: 0, color: '#f9fafb' }}>
            Report History
          </h1>
          <p style={{ color: '#6b7280', margin: '4px 0 0', fontSize: '0.87rem' }}>
            {reports.length} report{reports.length !== 1 ? 's' : ''} saved
          </p>
        </div>
        <button id="btn-refresh-history" className="btn-ghost" onClick={load}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {reports.length === 0 ? (
        <div className="glass-card" style={{ padding: 60, textAlign: 'center', color: '#6b7280' }}>
          <FileText size={48} style={{ margin: '0 auto 16px', opacity: 0.3 }} />
          <p style={{ fontWeight: 500, marginBottom: 8 }}>No reports yet</p>
          <p style={{ fontSize: '0.85rem' }}>Analyse a document to see results here.</p>
        </div>
      ) : (
        <div className="history-layout" style={{ display: 'grid', gridTemplateColumns: selected ? 'minmax(0, 340px) minmax(0, 1fr)' : 'minmax(0, 1fr)', gap: 20, alignItems: 'start' }}>
          {/* List */}
          <div>
            {visibleReports.map(row => {
              const input = inputDetails(row.input_type)
              const summaryLine = row.summary?.split('\n').find(line => line.trim()) || 'No summary available.'
              return (
              <div
                key={row.id}
                id={`report-row-${row.id}`}
                className="glass-card-hover"
                onClick={() => openReport(row)}
                style={{
                  padding: '16px 20px', marginBottom: 10, cursor: 'pointer',
                  border: selected?.id === row.id ? '1px solid rgba(59,130,246,0.5)' : undefined,
                  boxShadow: selected?.id === row.id ? '0 0 20px rgba(59,130,246,0.15)' : undefined,
                }}
              >
                <div className="flex items-center gap-3">
                  <span style={{ fontSize: '1.4rem' }}>{input.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.88rem', color: '#e5e7eb',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {input.label}{row.original_filename ? ` · ${row.original_filename}` : ''}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: 2 }}>
                      {new Date(row.created_at).toLocaleString()}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#9ca3af', marginTop: 6,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={summaryLine}>
                      {summaryLine}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: '#6b7280', marginTop: 4 }}>
                      ID {row.id.slice(0, 8)}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {statusBadge(row.status)}
                    <div className="flex items-center gap-1">
                      <button
                        id={`btn-delete-${row.id}`}
                        className="btn-danger"
                        style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                        onClick={e => handleDelete(row.id, e)}
                        disabled={deleting === row.id}
                      >
                        {deleting === row.id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                      </button>
                      <ChevronRight size={14} color="#6b7280" />
                    </div>
                  </div>
                </div>
                {row.error_message && (
                  <div style={{ fontSize: '0.78rem', color: '#f87171', marginTop: 8, paddingTop: 8,
                    borderTop: '1px solid rgba(239,68,68,0.2)' }}>
                    {row.error_message}
                  </div>
                )}
              </div>
              )
            })}
            {visibleCount < reports.length && (
              <button
                className="btn-ghost"
                style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}
                onClick={() => setVisibleCount(count => count + PAGE_SIZE)}
              >
                Load more ({reports.length - visibleCount} remaining)
              </button>
            )}
          </div>

          {/* Detail panel */}
          {selected && (
            <div className="glass-card slide-in scrollbar-thin" style={{ padding: 24, position: 'sticky', top: 84, maxHeight: 'calc(100vh - 100px)', overflowY: 'auto' }}>
              <div className="flex items-center justify-between mb-5">
                <h2 style={{ fontWeight: 700, fontSize: '1rem', margin: 0, color: '#f9fafb' }}>
                  {selected.original_filename || `Report ${selected.id.slice(0, 8)}`}
                </h2>
                <button
                  id="btn-close-report-panel"
                  className="btn-ghost"
                  style={{ padding: '6px 10px' }}
                  onClick={() => setSelected(null)}
                >
                  ✕
                </button>
              </div>
              {selected.report ? (
                <ReportView report={selected.report} status={selected.status} />
              ) : selected.error_message ? (
                <div className="critical-alert">
                  <div style={{ fontWeight: 600, color: '#ef4444', marginBottom: 4 }}>Analysis Failed</div>
                  <div style={{ color: '#fca5a5', fontSize: '0.85rem' }}>{selected.error_message}</div>
                </div>
              ) : (
                <div style={{ color: '#6b7280', fontSize: '0.87rem' }}>No report data available.</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
