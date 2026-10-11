import { Navigate, NavLink, Route, Routes } from 'react-router-dom';
import DocumentQueuePage from '@/pages/DocumentQueuePage';
import DocumentUploadPage from '@/pages/DocumentUploadPage';
import DocumentDetailPage from '@/pages/DocumentDetailPage';
import InvoiceReviewPage from '@/pages/InvoiceReviewPage';
import DmsOnboardingPage from '@/pages/DmsOnboardingPage';

const mockMode = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_API === 'true';

function App() {
  return (
    <div className="shell">
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <aside className="shell__nav" aria-label="Primary navigation">
        <div className="brand">
          <div className="brand__logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
          </div>
          <div className="brand__text">
            <div className="brand__title-row">
              <strong>OneDMS</strong>
              <span className="brand__pill">EDI HUB</span>
            </div>
            <p>Intelligent Document Platform</p>
          </div>
        </div>

        <div className="nav-section">
          <span className="nav-section__label">CORE OPERATIONS</span>
          <nav>
            <NavLink
              to="/documents"
              className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
              end
            >
              <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="4" width="20" height="16" rx="2" />
                <path d="M7 15h10M7 9h10M7 12h4" />
              </svg>
              <span>Invoice Queue</span>
            </NavLink>

            <NavLink
              to="/documents/new"
              className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
            >
              <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span>Invoice Intake</span>
            </NavLink>
          </nav>
        </div>

        <div className="nav-section">
          <span className="nav-section__label">SYSTEM INTEGRATIONS</span>
          <nav>
            <NavLink
              to="/integrations/dms/new"
              className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
            >
              <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
              <span>DMS Onboarding</span>
            </NavLink>
          </nav>
        </div>

        <div className="nav-footer">
          <div className="system-status">
            <span className="status-indicator-dot"></span>
            <div>
              <strong>Neon PostgreSQL</strong>
              <p>Schema v2.4 • Connected</p>
            </div>
          </div>
          <div className="tenant-card">
            <span className="tenant-label">CONNECTED OEM GATEWAY</span>
            <div className="tenant-name">Daimler Truck Central ERP</div>
          </div>
        </div>

        {mockMode ? (
          <p className="mock-banner" role="status">
            Development fixture mode is ON.
          </p>
        ) : null}
      </aside>

      <main className="shell__main" id="workspace" tabIndex={-1}>
        <header className="workspace-band">
          <div className="workspace-band__left">
            <div className="breadcrumb">
              <span>OneDMS Platform</span>
              <span className="breadcrumb__sep">/</span>
              <strong className="breadcrumb__current">Central Invoicing Hub</strong>
            </div>
          </div>

          <div className="workspace-band__right">
            <div className="user-profile-badge">
              <span className="user-avatar">DT</span>
              <div className="user-info">
                <strong>OEM Auditor</strong>
                <small>Daimler Central Review</small>
              </div>
            </div>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Navigate to="/documents" replace />} />
          <Route path="/documents" element={<DocumentQueuePage />} />
          <Route path="/documents/new" element={<DocumentUploadPage />} />
          <Route path="/integrations/dms/new" element={<DmsOnboardingPage />} />
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
          <Route path="/invoices/:invoiceId" element={<InvoiceReviewPage />} />
          <Route path="*" element={<Navigate to="/documents" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
