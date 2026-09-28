import { useState, useRef, useCallback } from 'react'
import { FileText, Image, Upload, X, AlertCircle, CheckCircle2, Sparkles } from 'lucide-react'
import { analyzeText, analyzeFile } from '../api'
import type { ReportRow } from '../types'

const SAMPLE_TEXT = `Patient Jane Smith, 52 yo female. Chief complaint: productive cough, fever 38.8 C, HR 98, BP 130/85. History of penicillin allergy. Prescribed Amoxicillin 500mg TID. Impression: Community-acquired pneumonia.`

interface AnalyzeFormProps {
  onResult: (report: ReportRow) => void
}

type Tab = 'text' | 'file'
type Status = 'idle' | 'loading' | 'success' | 'error'

export default function AnalyzeForm({ onResult }: AnalyzeFormProps) {
  const [tab, setTab] = useState<Tab>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleTextSubmit = async () => {
    if (!text.trim()) return
    setStatus('loading')
    setErrorMsg('')
    try {
      const result = await analyzeText(text.trim())
      setStatus('success')
      onResult(result)
    } catch (e: unknown) {
      setStatus('error')
      setErrorMsg((e as Error).message || 'Analysis failed.')
    }
  }

  const handleFileSubmit = async () => {
    if (!file) return
    setStatus('loading')
    setErrorMsg('')
    try {
      const result = await analyzeFile(file)
      setStatus('success')
      onResult(result)
    } catch (e: unknown) {
      setStatus('error')
      setErrorMsg((e as Error).message || 'Upload failed.')
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) { setFile(f); setTab('file') }
  }, [])

  const clearFile = () => {
    setFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const isLoading = status === 'loading'

  return (
    <div className="glass-card p-8 slide-in" style={{ maxWidth: 720, margin: '0 auto' }}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(99,102,241,0.2))',
          border: '1px solid rgba(59,130,246,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Sparkles size={20} color="#60a5fa" />
        </div>
        <div>
          <h2 style={{ fontWeight: 700, fontSize: '1.1rem', margin: 0, color: '#f9fafb' }}>
            Submit Clinical Document
          </h2>
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#6b7280' }}>
            Text, PDF, or image (typed, scanned, or handwritten)
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6" style={{ background: 'rgba(17,24,39,0.6)', borderRadius: 12, padding: 4 }}>
        <button
          id="tab-text"
          onClick={() => setTab('text')}
          className={`tab-btn flex items-center gap-2 flex-1 ${tab === 'text' ? 'active' : ''}`}
        >
          <FileText size={15} /> Plain Text
        </button>
        <button
          id="tab-file"
          onClick={() => setTab('file')}
          className={`tab-btn flex items-center gap-2 flex-1 ${tab === 'file' ? 'active' : ''}`}
        >
          <Image size={15} /> PDF / Image
        </button>
      </div>

      {/* Text input */}
      {tab === 'text' && (
        <div className="fade-in">
          <textarea
            id="clinical-text-input"
            className="input-field scrollbar-thin"
            rows={8}
            placeholder="Paste clinical notes, discharge summaries, consultation letters…"
            value={text}
            onChange={e => { setText(e.target.value); setStatus('idle') }}
          />
          <div className="flex justify-between items-center mt-3">
            <button
              className="btn-ghost"
              style={{ fontSize: '0.8rem', padding: '6px 12px' }}
              onClick={() => setText(SAMPLE_TEXT)}
            >
              Load sample text
            </button>
            <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>{text.length} chars</span>
          </div>
          <button
            id="btn-analyze-text"
            className="btn-primary w-full mt-4"
            onClick={handleTextSubmit}
            disabled={isLoading || !text.trim()}
          >
            {isLoading ? <><div className="spinner" /> Analysing…</> : <><Sparkles size={16} /> Analyse Document</>}
          </button>
        </div>
      )}

      {/* File upload */}
      {tab === 'file' && (
        <div className="fade-in">
          <div
            className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !file && fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              id="file-upload-input"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f); setStatus('idle') }}
            />
            {!file ? (
              <>
                <Upload size={36} color="#3b82f6" style={{ margin: '0 auto 12px' }} />
                <p style={{ fontWeight: 600, color: '#f9fafb', marginBottom: 4 }}>
                  Drop file here or click to browse
                </p>
                <p style={{ fontSize: '0.82rem', color: '#6b7280' }}>
                  PDF, PNG, JPG, WEBP — up to 10 MB · 6 pages max
                </p>
              </>
            ) : (
              <div className="flex items-center gap-3 justify-center">
                <div style={{
                  padding: '8px 16px', borderRadius: 10,
                  background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
                  color: '#60a5fa', fontWeight: 500,
                }}>
                  📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)
                </div>
                <button
                  id="btn-clear-file"
                  className="btn-ghost"
                  style={{ padding: '8px 10px' }}
                  onClick={e => { e.stopPropagation(); clearFile() }}
                >
                  <X size={15} />
                </button>
              </div>
            )}
          </div>
          <button
            id="btn-analyze-file"
            className="btn-primary w-full mt-4"
            onClick={handleFileSubmit}
            disabled={isLoading || !file}
          >
            {isLoading ? <><div className="spinner" /> Processing…</> : <><Upload size={16} /> Upload &amp; Analyse</>}
          </button>
        </div>
      )}

      {/* Status feedback */}
      {status === 'error' && (
        <div className="critical-alert mt-4 fade-in flex items-start gap-3">
          <AlertCircle size={18} color="#ef4444" style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontWeight: 600, color: '#ef4444', fontSize: '0.9rem' }}>Analysis Failed</div>
            <div style={{ color: '#fca5a5', fontSize: '0.83rem', marginTop: 2 }}>{errorMsg}</div>
          </div>
        </div>
      )}
      {status === 'success' && (
        <div className="fade-in mt-4 flex items-center gap-2" style={{
          background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
          borderRadius: 10, padding: '12px 16px', color: '#10b981',
        }}>
          <CheckCircle2 size={18} />
          <span style={{ fontWeight: 500, fontSize: '0.9rem' }}>Analysis complete — report shown below</span>
        </div>
      )}
    </div>
  )
}
