/**
 * API types — mirror the Pydantic schemas from the backend.
 */

export interface EvidenceItem {
  text: string
  evidence?: string | null
  confidence: 'high' | 'medium' | 'low'
  source?: string | null
}

export interface MedicationItem {
  text: string
  name?: string | null
  dose?: string | null
  route?: string | null
  frequency?: string | null
  evidence?: string | null
  confidence: 'high' | 'medium' | 'low'
  source?: string | null
}

export interface VitalSign {
  text: string
  evidence?: string | null
  confidence: 'high' | 'medium' | 'low'
}

export interface VitalsPanel {
  hr?: VitalSign | null
  bp?: VitalSign | null
  temp?: VitalSign | null
  rr?: VitalSign | null
  spo2?: VitalSign | null
  weight?: VitalSign | null
  height?: VitalSign | null
}

export interface PatientInformation {
  name?: string | null
  age?: string | null
  sex?: string | null
  mrn?: string | null
  date_of_visit?: string | null
  evidence?: string | null
  confidence: 'high' | 'medium' | 'low'
}

export interface DocumentQuality {
  readable: boolean
  overall_confidence: 'high' | 'medium' | 'low'
  notes?: string | null
}

export interface AnalysisReport {
  report_summary: string
  patient_information: PatientInformation
  diagnoses: EvidenceItem[]
  symptoms: EvidenceItem[]
  clinical_observations: EvidenceItem[]
  medications: MedicationItem[]
  allergies: EvidenceItem[]
  vitals?: VitalsPanel | null
  missing_information: EvidenceItem[]
  potential_inconsistencies: EvidenceItem[]
  requires_review: EvidenceItem[]
  document_quality: DocumentQuality
}

export interface ReportRow {
  id: string
  created_at: string
  status: 'processing' | 'completed' | 'completed_with_warnings' | 'no_clinical_content' | 'failed'
  input_type: 'text' | 'pdf' | 'image'
  original_filename?: string | null
  summary?: string | null
  extracted_text?: string | null
  report?: AnalysisReport | null
  error_message?: string | null
}

export interface ApiError {
  error: {
    code: string
    message: string
  }
}
