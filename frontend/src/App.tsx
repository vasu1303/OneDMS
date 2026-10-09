function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
      <div className="text-center space-y-8">
        {/* Logo mark */}
        <div className="flex items-center justify-center gap-3">
          <div className="relative">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/25">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
            </div>
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-400 rounded-full border-2 border-slate-950 animate-pulse" />
          </div>
        </div>

        {/* Title */}
        <div className="space-y-3">
          <h1 className="text-5xl font-bold tracking-tight">
            <span className="text-white">One</span>
            <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">DMS</span>
          </h1>
          <p className="text-xl text-emerald-400 font-medium tracking-wide">
            ✓ Ready and Running
          </p>
        </div>

        {/* Subtitle */}
        <p className="text-slate-400 text-base max-w-md mx-auto leading-relaxed">
          Unified Dealer Management System — standardizing 80+ DMS formats into one canonical view.
        </p>

        {/* Status cards */}
        <div className="flex gap-4 justify-center pt-2">
          <StatusCard label="Frontend" port="5173" status="online" />
          <StatusCard label="Backend" port="8000" status="pending" />
          <StatusCard label="Pipeline" port="—" status="pending" />
        </div>

        {/* Tech stack */}
        <div className="flex gap-3 justify-center pt-4">
          {['React', 'TypeScript', 'Tailwind', 'FastAPI', 'PySpark'].map((tech) => (
            <span
              key={tech}
              className="px-3 py-1 text-xs font-medium text-slate-400 bg-slate-800/50 rounded-full border border-slate-700/50"
            >
              {tech}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function StatusCard({ label, port, status }: { label: string; port: string; status: 'online' | 'pending' }) {
  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl px-5 py-3 text-left min-w-[130px]">
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-slate-500'}`} />
        <span className="text-sm font-medium text-slate-200">{label}</span>
      </div>
      <span className="text-xs text-slate-500 font-mono">:{port}</span>
    </div>
  )
}

export default App
