import { useState } from 'react'
import Navbar from './components/Navbar'
import AnalyzeForm from './components/AnalyzeForm'
import ReportView from './components/ReportView'
import HistoryPage from './components/HistoryPage'
import type { ReportRow } from './types'
import { Sparkles } from 'lucide-react'

type Page = 'analyze' | 'history'

function HeroSection() {
  return (
    <div style={{ textAlign: 'center', padding: '60px 20px 40px', position: 'relative' }}>
      {/* Background glow */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -60%)',
        width: 600, height: 300,
        background: 'radial-gradient(ellipse at center, rgba(59,130,246,0.12) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />
      <div style={{ position: 'relative' }}>
        <div className="flex items-center justify-center gap-2 mb-4">
          <div style={{ height: 1, width: 40, background: 'linear-gradient(to right, transparent, rgba(59,130,246,0.5))' }} />
          <span style={{ fontSize: '0.72rem', letterSpacing: '0.15em', textTransform: 'uppercase',
            color: '#6b7280', fontWeight: 600 }}>
            AI-Powered Clinical Analysis
          </span>
          <div style={{ height: 1, width: 40, background: 'linear-gradient(to left, transparent, rgba(59,130,246,0.5))' }} />
        </div>
        <h1 style={{
          fontSize: 'clamp(2rem, 5vw, 3rem)', fontWeight: 800,
          background: 'linear-gradient(135deg, #f9fafb, #9ca3af)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          marginBottom: 16, lineHeight: 1.2,
        }}>
          Clinical Document Reviewer
        </h1>
        <p style={{ color: '#9ca3af', fontSize: '1.05rem', maxWidth: 520, margin: '0 auto' }}>
          Submit clinical notes, PDFs, or images. Get a structured report with
          AI extraction, hallucination checks, and safety alerts.
        </p>
        <div className="flex items-center justify-center gap-4 mt-6" style={{ flexWrap: 'wrap' }}>
          {['Gemini Flash AI', 'Hallucination Guard', 'Allergy Conflict Detection', 'Evidence Tracing'].map(f => (
            <div key={f} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: '0.78rem', color: '#6b7280',
            }}>
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#3b82f6', flexShrink: 0 }} />
              {f}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState<Page>('analyze')
  const [result, setResult] = useState<ReportRow | null>(null)

  const handleResult = (r: ReportRow) => {
    setResult(r)
  }

  const handleNewAnalysis = () => {
    setResult(null)
  }

  return (
    <div className="animated-gradient-bg" style={{ minHeight: '100vh' }}>
      <Navbar currentPage={page} onNav={p => { setPage(p); if (p === 'analyze') setResult(null) }} />

      <main style={{ padding: '0 20px 80px' }}>
        {page === 'analyze' ? (
          <>
            {!result && <HeroSection />}
            <div style={{ maxWidth: 1100, margin: '0 auto' }}>
              {!result ? (
                <AnalyzeForm onResult={handleResult} />
              ) : (
                <div>
                  {/* Top bar for new analysis */}
                  <div className="flex items-center justify-between mb-6 fade-in">
                    <div>
                      <h2 style={{ fontWeight: 700, fontSize: '1.2rem', margin: 0, color: '#f9fafb' }}>
                        Analysis Report
                      </h2>
                      <p style={{ color: '#6b7280', margin: '4px 0 0', fontSize: '0.82rem' }}>
                        {result.original_filename
                          ? `File: ${result.original_filename}`
                          : `Text input · ${new Date(result.created_at).toLocaleString()}`}
                      </p>
                    </div>
                    <div className="flex gap-3">
                      <button
                        id="btn-new-analysis"
                        className="btn-primary"
                        onClick={handleNewAnalysis}
                      >
                        <Sparkles size={15} /> New Analysis
                      </button>
                      <button
                        className="btn-ghost"
                        onClick={() => setPage('history')}
                      >
                        View History
                      </button>
                    </div>
                  </div>
                  {result.report && <ReportView report={result.report} status={result.status} />}
                  {result.error_message && (
                    <div className="critical-alert">
                      <div style={{ fontWeight: 600, color: '#ef4444' }}>Analysis Failed</div>
                      <div style={{ color: '#fca5a5', fontSize: '0.87rem', marginTop: 4 }}>{result.error_message}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ maxWidth: 1100, margin: '40px auto 0' }}>
            <HistoryPage />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{
        borderTop: '1px solid rgba(55,65,81,0.3)',
        padding: '20px', textAlign: 'center',
        fontSize: '0.78rem', color: '#4b5563',
      }}>
        AI Clinical Document Reviewer · All clinical data shown is synthetic ·
        Not intended for real clinical use
      </footer>
    </div>
  )
}
