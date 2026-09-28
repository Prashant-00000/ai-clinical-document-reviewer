import { useState } from 'react'
import type { EvidenceItem, MedicationItem, AnalysisReport } from '../types'
import {
  User, Pill, Activity, AlertTriangle, ShieldAlert,
  ClipboardList, Eye, Info, ThumbsUp, Stethoscope
} from 'lucide-react'

// ─── Helpers ────────────────────────────────────────────────────────────────

function ConfidencePip({ c }: { c: 'high' | 'medium' | 'low' }) {
  const color = c === 'high' ? '#10b981' : c === 'medium' ? '#f59e0b' : '#ef4444'
  return (
    <span
      title={`Confidence: ${c}`}
      style={{
        display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
        background: color, marginLeft: 5, verticalAlign: 'middle', flexShrink: 0,
      }}
    />
  )
}

function EvidenceTag({ evidence }: { evidence?: string | null }) {
  if (!evidence || evidence === 'not documented' || evidence === 'N/A') return null
  return (
    <span className="evidence-quote">"{evidence}"</span>
  )
}

function ItemRow({ item }: { item: EvidenceItem }) {
  return (
    <div style={{ marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid rgba(55,65,81,0.3)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
        <span style={{ fontSize: '0.88rem', color: '#e5e7eb', flex: 1 }}>{item.text}</span>
        <ConfidencePip c={item.confidence} />
      </div>
      <EvidenceTag evidence={item.evidence} />
    </div>
  )
}

function MedRow({ med }: { med: MedicationItem }) {
  const parts = [med.dose, med.route, med.frequency].filter(Boolean)
  return (
    <div style={{ marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid rgba(55,65,81,0.3)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
        <div style={{ flex: 1 }}>
          <span style={{ fontWeight: 600, color: '#e5e7eb', fontSize: '0.88rem' }}>
            {med.name || med.text}
          </span>
          {parts.length > 0 && (
            <span style={{ color: '#9ca3af', fontSize: '0.82rem', marginLeft: 8 }}>
              {parts.join(' · ')}
            </span>
          )}
        </div>
        <ConfidencePip c={med.confidence} />
      </div>
      <EvidenceTag evidence={med.evidence} />
    </div>
  )
}

function VitalCard({ label, item }: { label: string; item?: { text: string; confidence: string } | null }) {
  if (!item) return (
    <div style={{
      background: 'rgba(17,24,39,0.6)', borderRadius: 10, padding: '14px 16px',
      border: '1px solid rgba(55,65,81,0.3)', textAlign: 'center',
    }}>
      <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: '0.9rem', color: '#4b5563' }}>—</div>
    </div>
  )
  return (
    <div style={{
      background: 'rgba(59,130,246,0.05)', borderRadius: 10, padding: '14px 16px',
      border: '1px solid rgba(59,130,246,0.2)', textAlign: 'center',
    }}>
      <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: '1rem', fontWeight: 600, color: '#e5e7eb' }}>{item.text}</div>
    </div>
  )
}

// ─── Section container ───────────────────────────────────────────────────────

interface SectionProps {
  title: string
  icon: React.ReactNode
  count?: number
  children: React.ReactNode
  accentColor?: string
  collapsible?: boolean
}

function Section({ title, icon, count, children, accentColor = '#3b82f6', collapsible = true }: SectionProps) {
  const [open, setOpen] = useState(true)
  return (
    <div className="report-section" style={{ marginBottom: 14 }}>
      <button
        onClick={() => collapsible && setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          background: 'none', border: 'none', cursor: collapsible ? 'pointer' : 'default',
          padding: 0, marginBottom: open ? 16 : 0, textAlign: 'left',
        }}
      >
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: `${accentColor}22`,
          border: `1px solid ${accentColor}44`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          {icon}
        </div>
        <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#e5e7eb', flex: 1 }}>{title}</span>
        {count !== undefined && (
          <span style={{
            fontSize: '0.75rem', fontWeight: 600, color: accentColor,
            background: `${accentColor}22`, padding: '2px 8px', borderRadius: 20,
          }}>{count}</span>
        )}
        {collapsible && (
          <span style={{ color: '#6b7280', fontSize: '0.8rem' }}>{open ? '▲' : '▼'}</span>
        )}
      </button>
      {open && children}
    </div>
  )
}

// ─── Report Summary ──────────────────────────────────────────────────────────

function ReportSummary({ summary }: { summary: string }) {
  const lines = summary.split('\n').filter(Boolean)
  const isCritical = lines[0]?.startsWith('CRITICAL FLAGS:') && !lines[0].includes('None identified')

  return (
    <div style={{
      background: isCritical
        ? 'linear-gradient(135deg, rgba(239,68,68,0.08), rgba(99,102,241,0.05))'
        : 'linear-gradient(135deg, rgba(59,130,246,0.08), rgba(99,102,241,0.05))',
      border: isCritical ? '1px solid rgba(239,68,68,0.3)' : '1px solid rgba(59,130,246,0.3)',
      borderRadius: 16, padding: 24, marginBottom: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Stethoscope size={18} color={isCritical ? '#ef4444' : '#60a5fa'} />
        <span style={{ fontWeight: 700, fontSize: '0.85rem', textTransform: 'uppercase',
          letterSpacing: '0.08em', color: isCritical ? '#ef4444' : '#60a5fa' }}>
          Report Summary
        </span>
      </div>
      {lines.map((line, i) => {
        const isCritLine = line.startsWith('CRITICAL FLAGS:')
        const isReviewLine = line.startsWith('Review Required:')
        return (
          <div key={i} style={{
            fontSize: '0.9rem', lineHeight: 1.7,
            color: isCritLine && !line.includes('None') ? '#fca5a5' : isReviewLine ? '#c4b5fd' : '#d1d5db',
            fontWeight: isCritLine ? 600 : 400,
            paddingLeft: isCritLine && !line.includes('None') ? 12 : 0,
            borderLeft: isCritLine && !line.includes('None') ? '3px solid #ef4444' : 'none',
          } as React.CSSProperties}>
            {line}
          </div>
        )
      })}
    </div>
  )
}

// ─── Main ReportView ─────────────────────────────────────────────────────────

interface ReportViewProps {
  report: AnalysisReport
  status?: 'processing' | 'completed' | 'completed_with_warnings' | 'no_clinical_content' | 'failed'
}

export default function ReportView({ report, status }: ReportViewProps) {
  const hasCriticalFlags = report.potential_inconsistencies.length > 0
  const quality = report.document_quality
  const qualityIsPoor = !quality.readable || quality.overall_confidence === 'low'
  const qualityBadgeClass = qualityIsPoor
    ? 'badge-danger'
    : quality.overall_confidence === 'medium'
      ? 'badge-warning'
      : 'badge-success'
  const qualityLabel = qualityIsPoor ? 'Poor quality' : 'Readable'
  const confidenceLabel = `${quality.overall_confidence[0].toUpperCase()}${quality.overall_confidence.slice(1)} confidence`

  return (
    <div className="slide-in" style={{ maxWidth: 860, margin: '0 auto' }}>
      {/* Document quality badge */}
      <div className="mb-5">
        <div>
          <span className={qualityBadgeClass}>
            Doc Quality: {qualityLabel} · {confidenceLabel}
          </span>
        </div>
        {quality.notes && (
          <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: 6 }}>
            {quality.notes}
          </div>
        )}
      </div>

      {status === 'no_clinical_content' && (
        <div className="info-alert mb-4 fade-in" role="status">
          <div style={{ fontWeight: 600, color: '#93c5fd' }}>
            This document doesn't appear to contain clinical information.
          </div>
          <div style={{ color: '#bfdbfe', fontSize: '0.87rem', marginTop: 4 }}>
            No patient data, diagnoses, symptoms, vitals, medications, or allergies were identified.
          </div>
        </div>
      )}

      {/* Summary */}
      <ReportSummary summary={report.report_summary} />

      {/* Critical flags */}
      {hasCriticalFlags && (
        <div className="critical-alert mb-4 fade-in">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert size={18} color="#ef4444" />
            <span style={{ fontWeight: 700, color: '#ef4444', fontSize: '0.9rem' }}>
              {report.potential_inconsistencies.length} Critical Flag{report.potential_inconsistencies.length !== 1 ? 's' : ''}
            </span>
          </div>
          {report.potential_inconsistencies.map((item, i) => (
            <div key={i} style={{ fontSize: '0.87rem', color: '#fca5a5', marginBottom: 6 }}>
              ⚠ {item.text}
            </div>
          ))}
        </div>
      )}

      {/* Requires review */}
      {report.requires_review.length > 0 && (
        <div className="warning-alert mb-4 fade-in">
          <div className="flex items-center gap-2 mb-3">
            <Eye size={17} color="#f59e0b" />
            <span style={{ fontWeight: 700, color: '#f59e0b', fontSize: '0.9rem' }}>
              {report.requires_review.length} Item{report.requires_review.length !== 1 ? 's' : ''} Require Review
            </span>
          </div>
          {report.requires_review.map((item, i) => (
            <div key={i} style={{ fontSize: '0.87rem', color: '#fde68a', marginBottom: 4 }}>
              • {item.text}
            </div>
          ))}
        </div>
      )}

      {/* Patient info */}
      <Section title="Patient Information" icon={<User size={15} color="#60a5fa" />} accentColor="#3b82f6" collapsible={false}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
          {[
            { label: 'Name', value: report.patient_information.name },
            { label: 'Age', value: report.patient_information.age },
            { label: 'Sex', value: report.patient_information.sex },
            { label: 'MRN', value: report.patient_information.id },
          ].filter(({ value }) => Boolean(value)).map(({ label, value }) => (
            <div key={label} style={{
              background: 'rgba(17,24,39,0.6)', borderRadius: 10, padding: '12px 14px',
              border: '1px solid rgba(55,65,81,0.3)',
            }}>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 500, color: '#e5e7eb' }}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Vitals */}
      {report.vitals && (
        <Section title="Vital Signs" icon={<Activity size={15} color="#10b981" />} accentColor="#10b981">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            {[
              { label: 'Heart Rate',      item: report.vitals.hr },
              { label: 'Blood Pressure',  item: report.vitals.bp },
              { label: 'Temperature',     item: report.vitals.temp },
              { label: 'Resp Rate',       item: report.vitals.rr },
              { label: 'SpO\u2082',       item: report.vitals.spo2 },
            ].filter(({ item }) => Boolean(item)).map(({ label, item }) => (
              <VitalCard key={label} label={label} item={item} />
            ))}
          </div>
        </Section>
      )}

      {/* Diagnoses */}
      <Section title="Diagnoses" icon={<Stethoscope size={15} color="#a78bfa" />} count={report.diagnoses.length} accentColor="#8b5cf6">
        {report.diagnoses.length ? report.diagnoses.map((d, i) => <ItemRow key={i} item={d} />) : <Empty />}
      </Section>

      {/* Symptoms */}
      <Section title="Symptoms" icon={<ClipboardList size={15} color="#60a5fa" />} count={report.symptoms.length} accentColor="#3b82f6">
        {report.symptoms.length ? report.symptoms.map((s, i) => <ItemRow key={i} item={s} />) : <Empty />}
      </Section>

      {/* Medications */}
      <Section title="Medications" icon={<Pill size={15} color="#34d399" />} count={report.medications.length} accentColor="#10b981">
        {report.medications.length ? report.medications.map((m, i) => <MedRow key={i} med={m} />) : <Empty />}
      </Section>

      {/* Allergies */}
      <Section title="Allergies" icon={<AlertTriangle size={15} color="#f59e0b" />} count={report.allergies.length} accentColor="#f59e0b">
        {report.allergies.length ? report.allergies.map((a, i) => <ItemRow key={i} item={a} />) : <Empty />}
      </Section>

      {/* Clinical observations */}
      {report.clinical_observations.length > 0 && (
        <Section title="Clinical Observations" icon={<Eye size={15} color="#67e8f9" />} count={report.clinical_observations.length} accentColor="#06b6d4">
          {report.clinical_observations.map((o, i) => <ItemRow key={i} item={o} />)}
        </Section>
      )}

      {/* Clinical concerns */}
      {report.clinical_concerns.length > 0 && (
        <Section title="Clinical Concerns" icon={<ShieldAlert size={15} color="#f87171" />} count={report.clinical_concerns.length} accentColor="#ef4444">
          {report.clinical_concerns.map((concern, i) => <ItemRow key={i} item={concern} />)}
        </Section>
      )}

      {/* Missing information */}
      <Section title="Missing Information" icon={<Info size={15} color="#fb923c" />} count={report.missing_information.length} accentColor="#f97316">
        {report.missing_information.length ? report.missing_information.map((m, i) => <ItemRow key={i} item={m} />) : (
          <div className="flex items-center gap-2" style={{ color: '#10b981', fontSize: '0.87rem' }}>
            <ThumbsUp size={15} /> All key fields documented
          </div>
        )}
      </Section>
    </div>
  )
}

function Empty() {
  return <div style={{ color: '#6b7280', fontSize: '0.85rem', fontStyle: 'italic' }}>None documented</div>
}
