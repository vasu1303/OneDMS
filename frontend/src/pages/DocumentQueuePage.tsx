import { Link, useSearchParams } from 'react-router-dom';
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

function DocumentQueuePage() {
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

  return (
    <section className="view">
      <header className="view__header">
        <div>
          <h1>Invoice queue</h1>
          <p className="muted">
            Inspect submitted invoices, resolve findings, and record review decisions.
          </p>
        </div>
        <Link to="/documents/new" className="button button--primary">
          Upload invoice
        </Link>
      </header>

      <div className="filters">
        <label>
          Processing
          <select
            value={filters.processing_status ?? 'all'}
            onChange={(event) => updateFilter('processing_status', event.target.value)}
          >
            {processingOptions.map((option) => (
              <option key={option} value={option}>
                {option === 'all' ? 'All processing states' : statusLabel(option)}
              </option>
            ))}
          </select>
        </label>

        <label>
          Validation
          <select
            value={filters.validation_status ?? 'all'}
            onChange={(event) => updateFilter('validation_status', event.target.value)}
          >
            {validationOptions.map((option) => (
              <option key={option} value={option}>
                {option === 'all' ? 'All validation states' : statusLabel(option)}
              </option>
            ))}
          </select>
        </label>

        <label>
          Review
          <select
            value={filters.review_status ?? 'all'}
            onChange={(event) => updateFilter('review_status', event.target.value)}
          >
            {reviewOptions.map((option) => (
              <option key={option} value={option}>
                {option === 'all' ? 'All review states' : statusLabel(option)}
              </option>
            ))}
          </select>
        </label>

        <label>
          Dealer code
          <input
            type="text"
            value={filters.dealer_code ?? ''}
            onChange={(event) => updateFilter('dealer_code', event.target.value)}
            placeholder="D-4512"
          />
        </label>

        <label>
          Search
          <input
            type="text"
            value={filters.q ?? ''}
            onChange={(event) => updateFilter('q', event.target.value)}
            placeholder="Filename, DMS, note"
          />
        </label>
      </div>

      <div className="actions"><button className="button button--secondary" onClick={() => setSearchParams({})} disabled={searchParams.size === 0}>Clear filters</button><button className="button button--secondary" onClick={() => void queueQuery.refetch()} disabled={queueQuery.isFetching}>{queueQuery.isFetching ? 'Refreshing…' : 'Refresh queue'}</button></div>

      {queueQuery.isLoading && <p className="panel" role="status">Loading submitted documents…</p>}

      {queueQuery.isError && (
        <div className="panel panel--error" role="alert"><p>Could not load queue: {queueQuery.error.message}</p><button className="button button--secondary" onClick={() => void queueQuery.refetch()} disabled={queueQuery.isFetching}>Retry queue</button></div>
      )}

      {queueQuery.isSuccess && queueQuery.data.length === 0 && (
        <div className="panel stack"><h2>{searchParams.size ? 'No matching documents' : 'No documents submitted'}</h2><p>{searchParams.size ? 'Clear the filters to return to the full queue, or submit another invoice.' : 'Upload a dealer invoice to start inspection.'}</p><div className="actions">{searchParams.size > 0 && <button className="button button--secondary" onClick={() => setSearchParams({})}>Clear filters</button>}<Link className="button button--primary" to="/documents/new">Upload invoice</Link></div></div>
      )}

      {queueQuery.isSuccess && queueQuery.data.length > 0 && (
        <div className="table-wrap">
          <table className="queue-table">
            <caption>{queueQuery.data.length} submitted document{queueQuery.data.length === 1 ? '' : 's'} in this view</caption>
            <thead>
              <tr>
                <th>Document</th>
                <th>Dealer / DMS</th>
                <th>Received</th>
                <th>Workflow</th>
                <th>Summary</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {queueQuery.data.map((item) => (
                <tr key={item.id}>
                  <td data-label="Document">
                    <strong className="code"><Link to={`/documents/${item.id}`}>#{item.id}</Link></strong>
                    <div className="muted">{item.source_filename || item.source_type}</div>
                    {item.invoice_id != null && <div className="muted code">Invoice #{item.invoice_id}</div>}
                  </td>
                  <td data-label="Dealer / DMS">
                    <strong>{item.dealer_name || item.dealer_code || 'Dealer not supplied'}</strong>
                    <div className="muted code">{item.dealer_code || 'Code not supplied'}</div>
                    <div className="muted">{item.dms_name || 'DMS not supplied'}</div>
                  </td>
                  <td data-label="Received">{formatDateTime(item.received_at)}</td>
                  <td data-label="Workflow">
                    <span className={`badge badge--${item.processing_status}`}>{statusLabel(item.processing_status)}</span>
                    <div className="status-detail">Validation: {statusLabel(item.validation_status)}<br />Review: {statusLabel(item.review_status)}</div>
                  </td>
                  <td data-label="Summary">
                    {item.summary || 'No workflow summary supplied.'}
                    {item.findings_count != null ? (
                      <div className="muted">{item.findings_count} finding{item.findings_count === 1 ? '' : 's'}</div>
                    ) : null}
                  </td>
                  <td data-label="Action">
                    {item.invoice_id ? (
                      <Link
                        to={`/invoices/${item.invoice_id}`}
                        aria-label={`Review invoice ${item.invoice_id}`}
                      >
                        Open review
                      </Link>
                    ) : (
                      <Link
                        to={`/documents/${item.id}`}
                        aria-label={`Inspect document ${item.id}`}
                      >
                        Open detail
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default DocumentQueuePage;
