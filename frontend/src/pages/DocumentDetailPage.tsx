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
    } catch { /* Mutation error is rendered below; no false navigation. */ }
  };

  if (!Number.isSafeInteger(documentId)) return <section className="view"><h1>Invalid document ID</h1><p>Use a positive numeric document identifier.</p><Link to="/documents">Back to queue</Link></section>;

  return (
    <section className="view">
      <header className="view__header">
        <div>
          <h1>Document detail</h1>
          <p className="muted">Track extraction progress and open the original source.</p>
        </div>
        <Link to="/documents" className="button button--secondary">
          Back to queue
        </Link>
      </header>

      {detailQuery.isLoading && <p className="panel" role="status">Loading document…</p>}

      {detailQuery.isError && (
        <div className="panel panel--error" role="alert"><p>Could not load document: {detailQuery.error.message}</p><button className="button button--secondary" onClick={() => void detailQuery.refetch()}>Retry document</button></div>
      )}

      {detailQuery.data ? (
        <div className="stack">
          <IntakeSummary dealer={detailQuery.data.dealer_name || detailQuery.data.dealer_code || 'Not supplied'} dms={detailQuery.data.dms_name || 'Not supplied'} format={detailQuery.data.source_type.toUpperCase()} mapping={`Review: ${statusLabel(detailQuery.data.review_status)}`} />
          <div className="panel stack">
            <h2>#{detailQuery.data.id}</h2>
            <p className="muted">
              Dealer: {detailQuery.data.dealer_name || detailQuery.data.dealer_code || 'Not supplied'}<br />DMS: {detailQuery.data.dms_name || 'Not supplied'}
            </p>
            <p className="muted">Received: {formatDateTime(detailQuery.data.received_at)}</p>

            <div className="status-row">
              <span className={`badge badge--${detailQuery.data.processing_status}`}>
                Processing: {statusLabel(detailQuery.data.processing_status)}
              </span>
              <span className={`badge badge--${detailQuery.data.validation_status}`}>
                Validation: {statusLabel(detailQuery.data.validation_status)}
              </span>
              <span className={`badge badge--${detailQuery.data.review_status}`}>
                Review: {statusLabel(detailQuery.data.review_status)}
              </span>
            </div>

            {detailQuery.data.last_error ? (
              <p className="panel panel--error" role="alert">
                {detailQuery.data.last_error}
              </p>
            ) : null}

            <div className="actions">
              {detailQuery.data.invoice_id ? (
                <Link
                  to={`/invoices/${detailQuery.data.invoice_id}`}
                  className="button button--primary"
                >
                  {detailQuery.data.review_status === 'approved' ? 'View approved invoice' : 'Open invoice review'}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => void triggerProcess()}
                  className="button button--primary"
                  disabled={processMutation.isPending || detailQuery.data.processing_status === 'processing'}
                >
                  {processMutation.isPending || detailQuery.data.processing_status === 'processing' ? 'Processing…' : detailQuery.data.processing_status === 'failed' ? 'Retry processing' : 'Start processing'}
                </button>
              )}
            </div>
            {processMutation.isError && <p className="panel panel--error" role="alert">Processing request failed: {processMutation.error.message}</p>}
            {processMutation.isSuccess && !processMutation.data.invoice_id && <p role="status">Processing request accepted. Waiting for the document workflow to report a result.</p>}
            {detailQuery.data.invoice_id && <ApprovedInvoiceDownload invoiceId={detailQuery.data.invoice_id} approved={detailQuery.data.review_status === 'approved'} />}
          </div>
          <SourcePreview documentId={detailQuery.data.id} />
        </div>
      ) : null}
    </section>
  );
}

export default DocumentDetailPage;
