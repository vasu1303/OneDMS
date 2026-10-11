import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMemo } from 'react';
import { useDocumentQueue } from '@/hooks/useInvoiceWorkflow';
import type {
  ProcessingStatus,
  QueueFilters,
  ReviewStatus,
  ValidationStatus,
} from '@/types';
import { formatDateTime, statusLabel } from '@/utils/format';

const processingOptions: Array<ProcessingStatus | 'all'> = [
  'all',
  'received',
  'processing',
  'processed',
  'review_required',
  'failed',
];

const validationOptions: Array<ValidationStatus | 'all'> = [
  'all',
  'pending',
  'valid',
  'warning',
  'invalid',
];

const reviewOptions: Array<ReviewStatus | 'all'> = [
  'all',
  'pending',
  'in_review',
  'approved',
  'rejected',
];

const coerceFilter = <T extends string>(
  value: string | null,
  options: readonly T[],
  fallback: T,
): T => {
  if (value && options.includes(value as T)) {
    return value as T;
  }
  return fallback;
};

const formatBadgeClass = (sourceType: string = '') => {
  const t = sourceType.toLowerCase();
  if (t.includes('pdf')) return 'format-tag format-tag--pdf';
  if (t.includes('xml')) return 'format-tag format-tag--xml';
  if (t.includes('excel') || t.includes('xls')) return 'format-tag format-tag--xls';
  if (t.includes('csv')) return 'format-tag format-tag--csv';
  if (t.includes('json') || t.includes('api')) return 'format-tag format-tag--json';
  return 'format-tag';
};

function DocumentQueuePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: QueueFilters = useMemo(
    () => ({
      processing_status: coerceFilter(
        searchParams.get('processing_status'),
        processingOptions,
        'all',
      ),
      validation_status: coerceFilter(
        searchParams.get('validation_status'),
        validationOptions,
        'all',
      ),
      review_status: coerceFilter(searchParams.get('review_status'), reviewOptions, 'all'),
      dealer_code: searchParams.get('dealer_code') ?? '',
      q: searchParams.get('q') ?? '',
    }),
    [searchParams],
  );

  const queueQuery = useDocumentQueue(filters);

  const updateFilter = (name: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (!value || value === 'all') {
      next.delete(name);
    } else {
      next.set(name, value);
    }
    setSearchParams(next, { replace: true });
  };

  // Compute KPIs from queue items
  const stats = useMemo(() => {
    const data = queueQuery.data ?? [];
    const total = data.length;
    const reviewNeeded = data.filter((d) => d.processing_status === 'review_required' || d.review_status === 'in_review').length;
    const completed = data.filter((d) => d.processing_status === 'processed').length;
    const processingOrFailed = data.filter((d) => d.processing_status === 'failed' || d.processing_status === 'processing' || d.processing_status === 'received').length;

    return { total, reviewNeeded, completed, processingOrFailed };
  }, [queueQuery.data]);

  return (
    <section className="view queue-view">
      {/* Top Page Header */}
      <header className="view__header">
        <div>
          <div className="view__eyebrow">
            <span>INBOUND DISPATCH</span>
          </div>
          <h1>Dealer Invoice Queue</h1>
          <p className="muted">
            Standardize, inspect, and approve multi-format inbound dealer invoices for Daimler ERP ingestion.
          </p>
        </div>
        <div className="view__header-actions">
          <Link to="/documents/new" className="button button--primary">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Upload Invoice</span>
          </Link>
        </div>
      </header>

      {/* KPI Overview Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card__header">
            <span className="kpi-card__title">Total Inbound</span>
            <span className="kpi-card__icon kpi-card__icon--blue">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
            </span>
          </div>
          <div className="kpi-card__value">{queueQuery.isLoading ? '—' : stats.total}</div>
          <div className="kpi-card__subtitle">Multi-format dealership submissions</div>
        </div>

        <div className="kpi-card kpi-card--warning">
          <div className="kpi-card__header">
            <span className="kpi-card__title">Action Required</span>
            <span className="kpi-card__icon kpi-card__icon--amber">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </span>
          </div>
          <div className="kpi-card__value text-amber">{queueQuery.isLoading ? '—' : stats.reviewNeeded}</div>
          <div className="kpi-card__subtitle">Requires auditor decision & validation</div>
        </div>

        <div className="kpi-card kpi-card--success">
          <div className="kpi-card__header">
            <span className="kpi-card__title">Auto-Reconciled</span>
            <span className="kpi-card__icon kpi-card__icon--green">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </span>
          </div>
          <div className="kpi-card__value text-green">{queueQuery.isLoading ? '—' : stats.completed}</div>
          <div className="kpi-card__subtitle">Valid canonical records ready for OEM</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card__header">
            <span className="kpi-card__title">Intake & Exceptions</span>
            <span className="kpi-card__icon kpi-card__icon--purple">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </span>
          </div>
          <div className="kpi-card__value">{queueQuery.isLoading ? '—' : stats.processingOrFailed}</div>
          <div className="kpi-card__subtitle">Pipeline queue / Syntax issues</div>
        </div>
      </div>

      {/* Filter Control Bar */}
      <div className="filters-container">
        <div className="filters-toolbar">
          <div className="filter-group filter-group--search">
            <div className="search-input-wrapper">
              <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                value={filters.q ?? ''}
                onChange={(event) => updateFilter('q', event.target.value)}
                placeholder="Search file name, invoice number, or notes..."
                aria-label="Search documents"
              />
            </div>
          </div>

          <div className="filter-group">
            <label htmlFor="filter-processing">Workflow State</label>
            <select
              id="filter-processing"
              value={filters.processing_status ?? 'all'}
              onChange={(event) => updateFilter('processing_status', event.target.value)}
            >
              {processingOptions.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All Workflow States' : statusLabel(option)}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="filter-validation">Validation</label>
            <select
              id="filter-validation"
              value={filters.validation_status ?? 'all'}
              onChange={(event) => updateFilter('validation_status', event.target.value)}
            >
              {validationOptions.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All Validations' : statusLabel(option)}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="filter-review">Auditor Review</label>
            <select
              id="filter-review"
              value={filters.review_status ?? 'all'}
              onChange={(event) => updateFilter('review_status', event.target.value)}
            >
              {reviewOptions.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All Review Statuses' : statusLabel(option)}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group filter-group--dealer">
            <label htmlFor="filter-dealer">Dealer Code</label>
            <input
              id="filter-dealer"
              type="text"
              value={filters.dealer_code ?? ''}
              onChange={(event) => updateFilter('dealer_code', event.target.value)}
              placeholder="e.g. DEMO-API"
            />
          </div>
        </div>

        <div className="filters-actions">
          {searchParams.size > 0 && (
            <button
              className="button button--ghost"
              onClick={() => setSearchParams({})}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
              <span>Reset Filters</span>
            </button>
          )}

          <button
            className="button button--secondary button--refresh"
            onClick={() => void queueQuery.refetch()}
            disabled={queueQuery.isFetching}
          >
            <svg
              className={queueQuery.isFetching ? 'spin' : ''}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            <span>{queueQuery.isFetching ? 'Refreshing…' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* Loading State */}
      {queueQuery.isLoading && (
        <div className="panel loading-panel" role="status">
          <div className="loader-spinner"></div>
          <p>Syncing submitted documents from PostgreSQL...</p>
        </div>
      )}

      {/* Error State */}
      {queueQuery.isError && (
        <div className="panel panel--error stack" role="alert">
          <div className="error-title-row">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <strong>Queue synchronization failure</strong>
          </div>
          <p>{queueQuery.error.message}</p>
          <div className="actions">
            <button className="button button--secondary" onClick={() => void queueQuery.refetch()}>
              Retry Connection
            </button>
          </div>
        </div>
      )}

      {/* Empty State */}
      {queueQuery.isSuccess && queueQuery.data.length === 0 && (
        <div className="panel empty-state stack">
          <div className="empty-state__icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>
          <h2>{searchParams.size ? 'No matching invoices found' : 'No invoices in intake queue'}</h2>
          <p className="muted">
            {searchParams.size
              ? 'Try widening your filters or clearing search terms to inspect the full list.'
              : 'Upload a dealer invoice in PDF, XML, Excel, CSV, or JSON format to trigger extraction.'}
          </p>
          <div className="actions">
            {searchParams.size > 0 && (
              <button className="button button--secondary" onClick={() => setSearchParams({})}>
                Clear Active Filters
              </button>
            )}
            <Link className="button button--primary" to="/documents/new">
              Upload New Invoice
            </Link>
          </div>
        </div>
      )}

      {/* Main Queue Data Table */}
      {queueQuery.isSuccess && queueQuery.data.length > 0 && (
        <div className="table-card">
          <div className="table-card__header">
            <div className="table-card__title-wrap">
              <strong>Inbound Invoices</strong>
              <span className="badge-count">{queueQuery.data.length} records</span>
            </div>
            <span className="table-card__hint">Ledger sorted by received timestamp</span>
          </div>

          <div className="table-wrap">
            <table className="queue-table">
              <thead>
                <tr>
                  <th>Document & File</th>
                  <th>Dealership & System</th>
                  <th>Received</th>
                  <th>Lifecycle Status</th>
                  <th>Extraction & Findings</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {queueQuery.data.map((item) => {
                  const targetUrl = item.invoice_id ? `/invoices/${item.invoice_id}` : `/documents/${item.id}`;
                  return (
                    <tr
                      key={item.id}
                      className="queue-row queue-row--clickable"
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest('a, button, input, select')) return;
                        navigate(targetUrl);
                      }}
                      title={`Click to open ${item.invoice_id ? `canonical invoice #${item.invoice_id}` : `document #${item.id}`}`}
                    >
                      {/* Document & File Column */}
                      <td data-label="Document & File">
                        <div className="doc-cell">
                          <div className="doc-cell__top">
                            <Link
                              to={`/documents/${item.id}`}
                              className="doc-id doc-id--link"
                              title="View document ingestion details"
                            >
                              #{item.id}
                            </Link>
                            <span className={formatBadgeClass(item.source_type)}>
                              {item.source_type.toUpperCase()}
                            </span>
                          </div>
                          <Link
                            to={targetUrl}
                            className="doc-filename-link"
                            title={item.source_filename || `payload_${item.id}.${item.source_type}`}
                          >
                            {item.source_filename || `payload_${item.id}.${item.source_type}`}
                          </Link>
                          {item.invoice_id != null && (
                            <div className="invoice-link">
                              <Link
                                to={`/invoices/${item.invoice_id}`}
                                className="invoice-tag invoice-tag--clickable"
                                title="Open canonical invoice record"
                              >
                                <span>Canonical Inv #{item.invoice_id}</span>
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                  <line x1="7" y1="17" x2="17" y2="7" />
                                  <polyline points="7 7 17 7 17 17" />
                                </svg>
                              </Link>
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Dealership & System Column */}
                      <td data-label="Dealership & System">
                        <div className="dealer-cell">
                          <strong className="dealer-name">
                            {item.dealer_name || item.dealer_code || 'Unknown Dealership'}
                          </strong>
                          <div className="dealer-sub-row">
                            <span className="dealer-code-pill">{item.dealer_code || `ID-${item.id}`}</span>
                            <span className="dms-name">{item.dms_name || 'Standard Ingestion'}</span>
                          </div>
                        </div>
                      </td>

                      {/* Received Column */}
                      <td data-label="Received">
                        <div className="timestamp-cell">
                          <span className="timestamp-primary">{formatDateTime(item.received_at)}</span>
                        </div>
                      </td>

                      {/* Lifecycle Status Column */}
                      <td data-label="Lifecycle Status">
                        <div className="status-cell">
                          <span className={`badge badge--${item.processing_status}`}>
                            <span className="badge-dot"></span>
                            <span>{statusLabel(item.processing_status)}</span>
                          </span>
                          <div className="sub-status-pills">
                            <span className={`mini-pill mini-pill--${item.validation_status}`}>
                              Val: {statusLabel(item.validation_status)}
                            </span>
                            <span className={`mini-pill mini-pill--${item.review_status}`}>
                              Rev: {statusLabel(item.review_status)}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Extraction Summary & Findings Column */}
                      <td data-label="Extraction & Findings">
                        <div className="summary-cell">
                          <p className="summary-text" title={item.summary || ''}>
                            {item.summary || 'Extraction ready for review.'}
                          </p>
                          {item.findings_count != null && item.findings_count > 0 && (
                            <span className="finding-flag">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10" />
                                <line x1="12" y1="8" x2="12" y2="12" />
                                <line x1="12" y1="16" x2="12.01" y2="16" />
                              </svg>
                              <span>{item.findings_count} {item.findings_count === 1 ? 'Finding' : 'Findings'}</span>
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Actions Column */}
                      <td data-label="Actions" className="text-right">
                        <div className="action-cell">
                          {item.invoice_id ? (
                            <div className="action-buttons-group">
                              <Link
                                to={`/invoices/${item.invoice_id}`}
                                className="button button--table-action button--table-action-primary"
                                aria-label={`Review canonical invoice ${item.invoice_id}`}
                              >
                                <span>Review</span>
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                  <polyline points="9 18 15 12 9 6" />
                                </svg>
                              </Link>
                              <Link
                                to={`/documents/${item.id}`}
                                className="button button--table-action button--ghost"
                                title="Inspect raw inbound payload"
                              >
                                <span>Payload</span>
                              </Link>
                            </div>
                          ) : (
                            <Link
                              to={`/documents/${item.id}`}
                              className="button button--table-action"
                              aria-label={`Inspect inbound document ${item.id}`}
                            >
                              <span>Inspect</span>
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="9 18 15 12 9 6" />
                              </svg>
                            </Link>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export default DocumentQueuePage;
