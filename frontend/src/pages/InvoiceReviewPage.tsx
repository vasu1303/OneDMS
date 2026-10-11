import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useBlocker, useParams } from 'react-router-dom';
import { useInvoiceDetail, usePatchInvoice, useReviewInvoice } from '@/hooks/useInvoiceWorkflow';
import SourcePreview from '@/components/common/SourcePreview';
import ApprovedInvoiceDownload from '@/components/common/ApprovedInvoiceDownload';
import Notice from '@/components/common/Notice';
import type { InvoiceDetail, InvoiceHeader, InvoiceLineItem } from '@/types';
import { formatMoney, parseRouteId, severityRank, statusLabel } from '@/utils/format';

const headerFields: Array<{ key: keyof InvoiceHeader; label: string; type?: string }> = [
  { key: 'invoice_number', label: 'Invoice Number' },
  { key: 'invoice_date', label: 'Invoice Date', type: 'date' },
  { key: 'dealer_invoice_ref', label: 'Dealer Reference Code' },
  { key: 'currency_code', label: 'Currency Code' },
  { key: 'subtotal_amount', label: 'Subtotal Amount', type: 'number' },
  { key: 'discount_amount', label: 'Discount Amount', type: 'number' },
  { key: 'tax_amount', label: 'Tax Total Amount', type: 'number' },
  { key: 'total_amount', label: 'Grand Total Amount', type: 'number' },
];

const lineFields: Array<{ key: keyof InvoiceLineItem; label: string; numeric?: boolean }> = [
  { key: 'part_number', label: 'Part Number / SKU' },
  { key: 'description', label: 'Description' },
  { key: 'vin', label: 'Chassis / VIN' },
  { key: 'quantity', label: 'Qty', numeric: true },
  { key: 'unit_price', label: 'Unit Price', numeric: true },
  { key: 'discount_amount', label: 'Discount', numeric: true },
  { key: 'tax_amount', label: 'Tax Amount', numeric: true },
  { key: 'line_total', label: 'Line Total', numeric: true },
];

type Draft = { header: Record<string, string>; lines: Array<Record<string, string>> };

const draftFrom = (invoice: InvoiceDetail): Draft => ({
  header: Object.fromEntries(headerFields.map(({ key }) => [key, String(invoice.header[key] ?? '')])),
  lines: invoice.line_items.map((line) => Object.fromEntries(lineFields.map(({ key }) => [key, String(line[key] ?? '')]))),
});

const numberValue = (value: string, label: string): number => {
  if (!value.trim() || !Number.isFinite(Number(value))) throw new Error(`${label} needs a finite numeric value.`);
  return Number(value);
};

export default function InvoiceReviewPage() {
  const { invoiceId: routeId } = useParams();
  const invoiceId = parseRouteId(routeId);
  const query = useInvoiceDetail(invoiceId);

  if (!Number.isSafeInteger(invoiceId)) {
    return (
      <section className="view">
        <div className="panel panel--error stack">
          <h2>Invalid Invoice Reference</h2>
          <p>Please provide a valid numeric invoice identifier.</p>
          <Link to="/documents" className="button button--secondary">Back to Queue</Link>
        </div>
      </section>
    );
  }

  if (!query.data) {
    return (
      <section className="view">
        <header className="view__header">
          <div>
            <h1>Canonical Invoice Review</h1>
            <p className="muted">Loading invoice record...</p>
          </div>
          <Link to="/documents" className="button button--secondary">Back to Queue</Link>
        </header>

        {query.isError ? (
          <div className="panel panel--error stack" role="alert">
            <p>{query.error.message}</p>
            <div className="actions">
              <button className="button button--secondary" onClick={() => void query.refetch()}>
                Retry Invoice
              </button>
            </div>
          </div>
        ) : (
          <div className="panel loading-panel" role="status">
            <div className="loader-spinner"></div>
            <p>Loading canonical invoice data from Neon PostgreSQL...</p>
          </div>
        )}
      </section>
    );
  }

  return <InvoiceEditor key={invoiceId} initialInvoice={query.data} />;
}

function InvoiceEditor({ initialInvoice }: { initialInvoice: InvoiceDetail }) {
  const [confirmed, setConfirmed] = useState(initialInvoice);
  const [draft, setDraft] = useState(() => draftFrom(initialInvoice));
  const [savedDraft, setSavedDraft] = useState(() => JSON.stringify(draftFrom(initialInvoice)));
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const patch = usePatchInvoice();
  const review = useReviewInvoice();

  const approved = confirmed.review_status === 'approved';
  const invalid = confirmed.validation_status === 'invalid';
  const busy = patch.isPending || review.isPending;
  const dirty = JSON.stringify(draft) !== savedDraft;

  const blocker = useBlocker(dirty || busy);

  useEffect(() => {
    if (blocker.state !== 'blocked') return;
    if (busy) { blocker.reset(); return; }
    if (window.confirm('Discard unsaved corrections and leave this invoice?')) blocker.proceed();
    else blocker.reset();
  }, [blocker, busy]);

  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    if (dirty || busy) window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty, busy]);

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || !dirty || approved) return;
    setError(''); setFeedback('');

    try {
      const header: InvoiceHeader = {
        invoice_number: draft.header.invoice_number,
        invoice_date: draft.header.invoice_date || null,
        dealer_invoice_ref: draft.header.dealer_invoice_ref || null,
        currency_code: draft.header.currency_code,
        subtotal_amount: numberValue(draft.header.subtotal_amount, 'Subtotal'),
        discount_amount: numberValue(draft.header.discount_amount, 'Discount'),
        tax_amount: numberValue(draft.header.tax_amount, 'Tax'),
        total_amount: numberValue(draft.header.total_amount, 'Total'),
      };

      const line_items = confirmed.line_items.map((line, index): InvoiceLineItem => {
        const fields = draft.lines[index];
        return {
          id: line.id,
          line_number: line.line_number,
          part_number: fields.part_number || null,
          description: fields.description || null,
          vin: fields.vin || null,
          quantity: numberValue(fields.quantity, `Line ${line.line_number} quantity`),
          unit_price: numberValue(fields.unit_price, `Line ${line.line_number} unit price`),
          discount_amount: numberValue(fields.discount_amount, `Line ${line.line_number} discount`),
          tax_amount: numberValue(fields.tax_amount, `Line ${line.line_number} tax`),
          line_total: numberValue(fields.line_total, `Line ${line.line_number} total`),
        };
      });

      const updated = await patch.mutateAsync({ invoiceId: confirmed.id, payload: { header, line_items } });
      setConfirmed(updated);
      const next = draftFrom(updated);
      setDraft(next);
      setSavedDraft(JSON.stringify(next));
      setFeedback('Corrections saved successfully. Canonical record and validations recomputed.');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not save corrections. Draft retained.');
    }
  };

  const decide = async (decision: 'approve' | 'reject') => {
    if (busy || dirty || approved || (decision === 'approve' && invalid)) return;
    const actionText = decision === 'approve' ? 'Approve' : 'Reject';
    if (!window.confirm(`${actionText} invoice ${confirmed.header.invoice_number || `#${confirmed.id}`} using saved canonical values?`)) return;

    setError(''); setFeedback('');
    try {
      const updated = await review.mutateAsync({ invoiceId: confirmed.id, payload: { decision } });
      setConfirmed(updated);
      const next = draftFrom(updated);
      setDraft(next);
      setSavedDraft(JSON.stringify(next));
      setFeedback(`Auditor decision recorded: ${statusLabel(updated.review_status)}.`);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The decision could not be recorded. Retry.');
    }
  };

  const findings = [...confirmed.findings].sort((left, right) => severityRank(left.severity) - severityRank(right.severity));

  return (
    <section className="view review-view">
      {/* Top Header */}
      <header className="view__header">
        <div>
          <div className="breadcrumb">
            <Link to="/documents">Invoice Queue</Link>
            <span className="breadcrumb__sep">/</span>
            <span>Document #{confirmed.document_id}</span>
            <span className="breadcrumb__sep">/</span>
            <strong>Invoice #{confirmed.id}</strong>
          </div>
          <div className="review-title-row">
            <h1>{confirmed.header.invoice_number || 'Unnamed Invoice'}</h1>
            <span className={`badge badge--${confirmed.review_status}`}>
              <span className="badge-dot"></span>
              <span>{statusLabel(confirmed.review_status)}</span>
            </span>
            <span className={`mini-pill mini-pill--${confirmed.validation_status}`}>
              Validation: {statusLabel(confirmed.validation_status)}
            </span>
          </div>
          <p className="muted">
            Inspect extracted invoice against raw dealer document, review validation findings, and finalize canonical record.
          </p>
        </div>
        <Link className="button button--secondary" to="/documents">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span>Back to Queue</span>
        </Link>
      </header>

      {/* KPI Ledger Strip */}
      <dl className="ledger-strip">
        <div className="ledger-cell">
          <dt>INBOUND SOURCE DOC</dt>
          <dd>
            <Link to={`/documents/${confirmed.document_id}`} className="ledger-link">
              #{confirmed.document_id}
            </Link>
          </dd>
        </div>

        <div className="ledger-cell">
          <dt>CANONICAL TOTAL</dt>
          <dd className="amount text-primary-amount">
            {formatMoney(confirmed.header.total_amount, confirmed.header.currency_code)}
          </dd>
        </div>

        <div className="ledger-cell">
          <dt>REVIEW DECISION</dt>
          <dd>
            <span className={`badge badge--${confirmed.review_status}`}>
              <span className="badge-dot"></span>
              <span>{statusLabel(confirmed.review_status)}</span>
            </span>
          </dd>
        </div>

        <div className="ledger-cell">
          <dt>VALIDATION FINDINGS</dt>
          <dd>
            <span className={findings.length > 0 ? 'text-amber' : 'text-green'}>
              {findings.length} {findings.length === 1 ? 'Finding' : 'Findings'}
            </span>
          </dd>
        </div>
      </dl>

      {approved && (
        <Notice kind="success">
          <div className="notice-content-row">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <strong>Invoice Approved & Canonical Record Locked. Ready for OEM Export.</strong>
          </div>
        </Notice>
      )}

      <ApprovedInvoiceDownload
        invoiceId={confirmed.id}
        invoiceNumber={confirmed.header.invoice_number}
        approved={approved}
      />

      {/* Main Split Review Grid */}
      <div className="review-grid">
        {/* Left Pane: Original Source */}
        <div className="source-panel-container">
          <div className="source-panel-header">
            <div className="source-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <strong>Retained Original Source</strong>
            </div>
            <span className="source-doc-badge">Document #{confirmed.document_id}</span>
          </div>
          <SourcePreview documentId={confirmed.document_id} />
        </div>

        {/* Right Pane: Canonical Editor */}
        <form className="canonical-panel stack" onSubmit={(event) => void save(event)}>
          <header className="canonical-header">
            <div>
              <h2>Canonical Invoice Record</h2>
              <p className="muted">
                {approved
                  ? 'Approved values. Corrections and reviews are locked.'
                  : dirty
                  ? 'Unsaved auditor edits. Save before recording approval.'
                  : 'Standardized canonical fields verified by OneDMS.'}
              </p>
            </div>
            {dirty && <span className="dirty-badge">Unsaved Changes</span>}
          </header>

          <fieldset disabled={busy || approved} className="stack">
            {/* Header Fields Section */}
            <div className="review-section">
              <h3 className="review-section-title">Invoice Header</h3>
              <div className="form-grid">
                {headerFields.map(({ key, label, type = 'text' }) => (
                  <label key={key}>
                    <span>{label}</span>
                    <input
                      type={type}
                      step={type === 'number' ? 'any' : undefined}
                      required={type === 'number' || key === 'invoice_number' || key === 'currency_code'}
                      value={draft.header[key]}
                      onChange={(event) => {
                        setFeedback('');
                        setDraft((current) => ({
                          ...current,
                          header: { ...current.header, [key]: event.target.value },
                        }));
                      }}
                    />
                  </label>
                ))}
              </div>
            </div>

            {/* Line Items Section */}
            <section className="line-ledger">
              <div className="line-ledger-header">
                <h3 className="review-section-title">Invoice Line Items ({confirmed.line_items.length})</h3>
                <span className="line-ledger-subtitle">Standardized parts and vehicles</span>
              </div>

              {confirmed.line_items.length === 0 && (
                <p className="muted empty-lines-box">No line items detected for this invoice.</p>
              )}

              {confirmed.line_items.map((line, index) => (
                <fieldset className="line-entry-card" key={line.id ?? line.line_number}>
                  <div className="line-entry-card__header">
                    <span className="line-badge">Line #{line.line_number}</span>
                    {draft.lines[index].vin && (
                      <span className="vin-tag">CHASSIS: {draft.lines[index].vin}</span>
                    )}
                  </div>

                  <div className="line-fields">
                    {lineFields.map(({ key, label, numeric }) => (
                      <label key={key} className={key === 'description' ? 'line-description' : ''}>
                        <span>{label}</span>
                        <input
                          aria-label={`Line ${line.line_number}: ${label}`}
                          className={numeric ? 'amount' : undefined}
                          type={numeric ? 'number' : 'text'}
                          step={numeric ? 'any' : undefined}
                          required={numeric}
                          value={draft.lines[index][key]}
                          onChange={(event) => {
                            setFeedback('');
                            setDraft((current) => ({
                              ...current,
                              lines: current.lines.map((fields, position) =>
                                position === index ? { ...fields, [key]: event.target.value } : fields,
                              ),
                            }));
                          }}
                        />
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </section>
          </fieldset>

          {/* Validation Findings Box */}
          <section className="findings-card" aria-labelledby="findings-heading">
            <div className="findings-header">
              <div className="findings-title-row">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <h3 id="findings-heading">Validation Diagnostic Findings ({findings.length})</h3>
              </div>
              <span className="findings-meta">Evaluated against 7 enterprise Daimler rules</span>
            </div>

            {findings.length === 0 ? (
              <div className="no-findings-box">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                <span>All checks passed! No reconciliation discrepancies detected.</span>
              </div>
            ) : (
              <ul className="findings-list">
                {findings.map((finding, index) => (
                  <li key={finding.id ?? index} className={`finding-item finding-item--${finding.severity}`}>
                    <div className="finding-heading">
                      <span className={`badge badge--${finding.severity}`}>
                        <span className="badge-dot"></span>
                        <span>{statusLabel(finding.severity)}</span>
                      </span>
                      <span className="finding-field-code">{finding.field || 'General Field'}</span>
                      {finding.line_number != null && (
                        <span className="finding-line-tag">Line #{finding.line_number}</span>
                      )}
                    </div>
                    <p className="finding-message">{finding.message}</p>
                    {finding.confidence != null && (
                      <span className="confidence-pill">
                        Confidence: {(finding.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {error && (
            <div className="panel panel--error" role="alert">
              <strong>Save Error: </strong> {error}
            </div>
          )}

          {/* Sticky Decision Bar */}
          {!approved && (
            <div className="decision-bar">
              <div className="decision-actions">
                <button
                  type="submit"
                  className="button button--secondary"
                  disabled={busy || !dirty}
                >
                  {patch.isPending ? 'Saving Corrections…' : 'Save Corrections'}
                </button>
                <button
                  type="button"
                  className="button button--danger"
                  disabled={busy || dirty}
                  onClick={() => void decide('reject')}
                >
                  Reject Invoice
                </button>
                <button
                  type="button"
                  className="button button--primary button--approve"
                  disabled={busy || dirty || invalid}
                  onClick={() => void decide('approve')}
                >
                  {review.isPending ? 'Recording Decision…' : 'Approve Invoice'}
                </button>
              </div>
              <p className="decision-hint muted">
                {busy
                  ? 'Processing transaction against Neon database...'
                  : dirty
                  ? 'You have unsaved changes. Save before recording an approval decision.'
                  : invalid
                  ? 'Approval blocked: Resolve validation discrepancies and save first.'
                  : 'Auditor approval will lock the record and deliver to Daimler ERP.'}
              </p>
            </div>
          )}

          {feedback && (
            <div className="save-feedback" role="status" aria-live="polite">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>{feedback}</span>
            </div>
          )}
        </form>
      </div>
    </section>
  );
}
