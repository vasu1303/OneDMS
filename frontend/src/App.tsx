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
          <div>
            <strong>OneDMS</strong>
            <p>Invoice review workspace</p>
          </div>
        </div>

        <nav>
          <NavLink
            to="/documents"
            className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
            end
          >
            Invoice queue
          </NavLink>
          <NavLink
            to="/documents/new"
            className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
          >
            Invoice intake
          </NavLink>
          <NavLink
            to="/integrations/dms/new"
            className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
          >
            DMS onboarding
          </NavLink>
        </nav>

        <div className="nav-footer"><strong>Invoice operations</strong><p>Upload, review, approve, and download.</p></div>

        {mockMode ? (
          <p className="mock-banner" role="status">
            Development fixture mode is ON.
          </p>
        ) : null}
      </aside>

      <main className="shell__main" id="workspace" tabIndex={-1}>
        <header className="workspace-band"><div><strong>Invoice operations</strong><span>Dealer invoices in one standard format</span></div></header>
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
