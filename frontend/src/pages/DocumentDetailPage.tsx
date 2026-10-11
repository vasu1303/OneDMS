import { Link, useNavigate, useParams } from 'react-router-dom';
import SourcePreview from '@/components/common/SourcePreview';
import ApprovedInvoiceDownload from '@/components/common/ApprovedInvoiceDownload';
import IntakeSummary from '@/components/common/IntakeSummary';
import { useDocumentDetail, useProcessDocument } from '@/hooks/useInvoiceWorkflow';
import { formatDateTime, parseRouteId, statusLabel } from '@/utils/format';

function DocumentDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const documentId = parseRouteId(params.documentId);

  const detailQuery = useDocumentDetail(documentId);
  const processMutation = useProcessDocument();

  const triggerProcess = async () => {
    try {
      const updated = await processMutation.mutateAsync(documentId);
      if (updated.invoice_id) navigate(`/invoices/${updated.invoice_id}`);
    } catch {
      // Handled via mutation state
    }
  };

  if (!Number.isSafeInteger(documentId)) {
    return (
      <section className="view">
        <div className="panel panel--error stack">
          <h2>Invalid Document Identifier</h2>
          <p>Please provide a valid numeric document reference.</p>
          <Link to="/documents" className="button button--secondary">Back to Queue</Link>
        </div>
      </section>
    );
  }

  return (
    <section className="view detail-view">
      <header className="view__header">
        <div>
          <div className="breadcrumb">
            <Link to="/documents">Invoice Queue</Link>
            <span className="breadcrumb__sep">/</span>
            <strong>Document #{documentId}</strong>
          </div>
          <h1>Inbound Document Inspection</h1>
          <p className="muted">
            Track extraction workflow stages, verify cryptographic checksums, and inspect raw payloads.
          </p>
        </div>
        <Link to="/documents" className="button button--secondary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span>Back to Queue</span>
        </Link>
      </header>

      {detailQuery.isLoading && (
        <div className="panel loading-panel" role="status">
          <div className="loader-spinner"></div>
          <p>Loading document metadata and lineage details...</p>
        </div>
      )}

      {detailQuery.isError && (
        <div className="panel panel--error stack" role="alert">
          <div className="error-title-row">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <strong>Document Load Failure</strong>
          </div>
          <p>{detailQuery.error.message}</p>
          <div className="actions">
            <button className="button button--secondary" onClick={() => void detailQuery.refetch()}>
              Retry
            </button>
          </div>
        </div>
      )}

      {detailQuery.data && (
        <div className="stack">
          {/* Intake Summary Pill */}
          <IntakeSummary
            dealer={detailQuery.data.dealer_name || detailQuery.data.dealer_code || 'Dealership not supplied'}
            dms={detailQuery.data.dms_name || 'Standard integration'}
            format={detailQuery.data.source_type.toUpperCase()}
            mapping={`Review State: ${statusLabel(detailQuery.data.review_status)}`}
          />

          {/* Master Detail Card */}
          <div className="panel doc-meta-card stack">
            <div className="doc-meta-card__header">
              <div className="doc-title-row">
                <span className="doc-hero-badge">INBOUND #{detailQuery.data.id}</span>
                <span className={`badge badge--${detailQuery.data.processing_status}`}>
                  <span className="badge-dot"></span>
                  <span>{statusLabel(detailQuery.data.processing_status)}</span>
                </span>
                <span className={`mini-pill mini-pill--${detailQuery.data.validation_status}`}>
                  Val: {statusLabel(detailQuery.data.validation_status)}
                </span>
              </div>
              <div className="doc-meta-actions">
                {detailQuery.data.invoice_id ? (
                  <Link
                    to={`/invoices/${detailQuery.data.invoice_id}`}
                    className="button button--primary"
                  >
                    <span>{detailQuery.data.review_status === 'approved' ? 'View Approved Invoice' : 'Open Canonical Review'}</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => void triggerProcess()}
                    className="button button--primary"
                    disabled={processMutation.isPending || detailQuery.data.processing_status === 'processing'}
                  >
                    {processMutation.isPending || detailQuery.data.processing_status === 'processing' ? (
                      <>
                        <span className="button-spinner"></span>
                        <span>Extracting Invoice...</span>
                      </>
                    ) : detailQuery.data.processing_status === 'failed' ? (
                      'Retry Pipeline Extraction'
                    ) : (
                      'Trigger Pipeline Extraction'
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Ingestion Facts Grid */}
            <div className="detail-facts-grid">
              <div className="fact-item">
                <span className="fact-label">Originating Dealer</span>
                <strong className="fact-value">{detailQuery.data.dealer_name || 'Not supplied'}</strong>
                <span className="fact-sub code">{detailQuery.data.dealer_code}</span>
              </div>

              <div className="fact-item">
                <span className="fact-label">Source System Profile</span>
                <strong className="fact-value">{detailQuery.data.dms_name || 'Not supplied'}</strong>
                <span className="fact-sub">{detailQuery.data.source_type.toUpperCase()} Integration</span>
              </div>

              <div className="fact-item">
                <span className="fact-label">Received At</span>
                <strong className="fact-value">{formatDateTime(detailQuery.data.received_at)}</strong>
                <span className="fact-sub">Neon Ingestion Log</span>
              </div>

              <div className="fact-item">
                <span className="fact-label">Original Filename</span>
                <strong className="fact-value code">{detailQuery.data.source_filename || 'Direct API Stream'}</strong>
                <span className="fact-sub">MIME: {detailQuery.data.source_content_type || 'auto-detected'}</span>
              </div>
            </div>

            {/* Error or Findings Note */}
            {detailQuery.data.last_error && (
              <div className="pipeline-error-box">
                <div className="error-title-row">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <strong>Pipeline Diagnostic Log</strong>
                </div>
                <p>{detailQuery.data.last_error}</p>
              </div>
            )}

            {detailQuery.data.invoice_id && (
              <div className="download-section">
                <ApprovedInvoiceDownload
                  invoiceId={detailQuery.data.invoice_id}
                  approved={detailQuery.data.review_status === 'approved'}
                />
              </div>
            )}
          </div>

          {/* Source Document Viewer */}
          <div className="preview-container-wrap">
            <SourcePreview documentId={detailQuery.data.id} />
          </div>
        </div>
      )}
    </section>
  );
}

export default DocumentDetailPage;
