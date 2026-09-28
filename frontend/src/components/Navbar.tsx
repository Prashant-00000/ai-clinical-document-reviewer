import { Activity, Stethoscope } from 'lucide-react'

interface NavbarProps {
  currentPage: 'analyze' | 'history'
  onNav: (page: 'analyze' | 'history') => void
}

export default function Navbar({ currentPage, onNav }: NavbarProps) {
  return (
    <nav className="sticky top-0 z-50" style={{
      background: 'rgba(10, 15, 30, 0.85)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(55, 65, 81, 0.3)',
    }}>
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <button
          onClick={() => onNav('analyze')}
          className="flex items-center gap-3 group"
          style={{ background: 'none', border: 'none', cursor: 'pointer' }}
        >
          <div style={{
            width: 40, height: 40, borderRadius: 12,
            background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 20px rgba(59,130,246,0.3)',
            transition: 'transform 0.2s, box-shadow 0.2s',
          }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.transform = 'scale(1.05)'
              ;(e.currentTarget as HTMLElement).style.boxShadow = '0 6px 30px rgba(59,130,246,0.5)'
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.transform = 'scale(1)'
              ;(e.currentTarget as HTMLElement).style.boxShadow = '0 4px 20px rgba(59,130,246,0.3)'
            }}
          >
            <Stethoscope size={20} color="white" />
          </div>
          <div className="text-left">
            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#f9fafb', lineHeight: 1.2 }}>
              AI Clinical Reviewer
            </div>
            <div style={{ fontSize: '0.7rem', color: '#6b7280', letterSpacing: '0.05em' }}>
              POWERED BY GEMINI
            </div>
          </div>
        </button>

        {/* Nav links */}
        <div className="flex items-center gap-2">
          <button
            id="nav-analyze"
            onClick={() => onNav('analyze')}
            className={`tab-btn ${currentPage === 'analyze' ? 'active' : ''}`}
          >
            <Activity size={16} style={{ display: 'inline', marginRight: 6 }} />
            Analyze
          </button>
          <button
            id="nav-history"
            onClick={() => onNav('history')}
            className={`tab-btn ${currentPage === 'history' ? 'active' : ''}`}
          >
            History
          </button>
        </div>
      </div>
    </nav>
  )
}
