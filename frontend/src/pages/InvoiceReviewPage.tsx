import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useBlocker, useParams } from 'react-router-dom';
import { useInvoiceDetail, usePatchInvoice, useReviewInvoice } from '@/hooks/useInvoiceWorkflow';
import SourcePreview from '@/components/common/SourcePreview';
import type { InvoiceDetail, InvoiceHeader, InvoiceLineItem } from '@/types';
import { formatMoney, parseRouteId, severityRank, statusLabel } from '@/utils/format';

const headerFields: Array<{ key: keyof InvoiceHeader; label: string; type?: string }> = [
  { key: 'invoice_number', label: 'Invoice number' },
  { key: 'invoice_date', label: 'Invoice date', type: 'date' },
  { key: 'dealer_invoice_ref', label: 'Dealer reference' },
  { key: 'currency_code', label: 'Currency code' },
  { key: 'subtotal_amount', label: 'Subtotal', type: 'number' },
  { key: 'discount_amount', label: 'Discount', type: 'number' },
  { key: 'tax_amount', label: 'Tax', type: 'number' },
  { key: 'total_amount', label: 'Canonical total', type: 'number' },
];
const lineFields: Array<{ key: keyof InvoiceLineItem; label: string; numeric?: boolean }> = [
  { key: 'part_number', label: 'Part number' },
  { key: 'description', label: 'Description' },
  { key: 'vin', label: 'VIN' },
  { key: 'quantity', label: 'Quantity', numeric: true },
  { key: 'unit_price', label: 'Unit price', numeric: true },
  { key: 'discount_amount', label: 'Discount', numeric: true },
  { key: 'tax_amount', label: 'Tax', numeric: true },
  { key: 'line_total', label: 'Line total', numeric: true },
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
  if (!Number.isSafeInteger(invoiceId)) return <section className="view"><h1>Invalid invoice ID</h1><p>Use a positive numeric invoice identifier.</p><Link to="/documents">Back to queue</Link></section>;
  if (!query.data) return <section className="view"><h1>Invoice review</h1>{query.isError
    ? <div className="panel panel--error" role="alert"><p>{query.error.message}</p><button className="button button--secondary" onClick={() => void query.refetch()}>Retry invoice</button></div>
    : <p role="status">Loading canonical invoice…</p>}<Link to="/documents">Back to queue</Link></section>;
  // Key only by identity, never by updated_at: refetches must not reset drafts.
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
    if (busy || !dirty) return;
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
        return { id: line.id, line_number: line.line_number,
          part_number: fields.part_number || null, description: fields.description || null, vin: fields.vin || null,
          quantity: numberValue(fields.quantity, `Line ${line.line_number} quantity`),
          unit_price: numberValue(fields.unit_price, `Line ${line.line_number} unit price`),
          discount_amount: numberValue(fields.discount_amount, `Line ${line.line_number} discount`),
          tax_amount: numberValue(fields.tax_amount, `Line ${line.line_number} tax`),
          line_total: numberValue(fields.line_total, `Line ${line.line_number} total`),
        };
      });
      const updated = await patch.mutateAsync({ invoiceId: confirmed.id, payload: { header, line_items } });
      setConfirmed(updated);
      const next = draftFrom(updated); setDraft(next); setSavedDraft(JSON.stringify(next));
      setFeedback('Corrections saved. The server response is now the canonical record.');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save corrections. Your draft is retained.'); }
  };
  const decide = async (decision: 'approve' | 'reject') => {
    if (busy || dirty) return;
    if (!window.confirm(`${decision === 'approve' ? 'Approve' : 'Reject'} invoice ${confirmed.header.invoice_number || `#${confirmed.id}`} using the saved canonical record?`)) return;
    setError(''); setFeedback('');
    try {
      const updated = await review.mutateAsync({ invoiceId: confirmed.id, payload: { decision } });
      setConfirmed(updated);
      const next = draftFrom(updated); setDraft(next); setSavedDraft(JSON.stringify(next));
      setFeedback(`Decision recorded. Review status: ${statusLabel(updated.review_status)}.`);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The decision could not be recorded. Retry.'); }
  };
  const findings = [...confirmed.findings].sort((left, right) => severityRank(left.severity) - severityRank(right.severity));
  return <section className="view review-view">
    <header className="view__header"><div><p className="orientation">Invoice inspection / #{confirmed.id}</p><h1>{confirmed.header.invoice_number || 'Invoice number missing'}</h1><p className="muted">Compare the retained original with the saved canonical record.</p></div><Link className="button button--secondary" to="/documents">Back to queue</Link></header>
    <dl className="ledger-strip"><div><dt>Document</dt><dd><Link to={`/documents/${confirmed.document_id}`}>#{confirmed.document_id}</Link></dd></div><div><dt>Canonical total</dt><dd className="amount">{formatMoney(confirmed.header.total_amount, confirmed.header.currency_code)}</dd></div><div><dt>Review</dt><dd>{statusLabel(confirmed.review_status)}</dd></div><div><dt>Validation</dt><dd>{statusLabel(confirmed.validation_status)}</dd></div></dl>
    <div className="review-grid">
      <SourcePreview documentId={confirmed.document_id} />
      <form className="canonical-panel stack" onSubmit={(event) => void save(event)}>
        <header><h2>Canonical record</h2><p className="muted">{dirty ? 'Unsaved corrections. Save before recording a decision.' : 'Saved values. Changes below remain a draft until saved.'}</p></header>
        <fieldset disabled={busy} className="stack"><legend className="sr-only">Invoice corrections</legend>
          <div className="form-grid">{headerFields.map(({ key, label, type = 'text' }) => <label key={key}>{label}<input type={type} step={type === 'number' ? 'any' : undefined} required={type === 'number' || key === 'invoice_number' || key === 'currency_code'} value={draft.header[key]} onChange={(event) => { setFeedback(''); setDraft((current) => ({ ...current, header: { ...current.header, [key]: event.target.value } })); }} /></label>)}</div>
          <section className="line-ledger"><h3>Invoice lines</h3>{confirmed.line_items.length === 0 && <p className="muted">No invoice lines supplied.</p>}{confirmed.line_items.map((line, index) => <fieldset className="line-entry" key={line.id ?? line.line_number}><legend>Line {line.line_number}</legend><div className="line-fields">{lineFields.map(({ key, label, numeric }) => <label key={key} className={key === 'description' ? 'line-description' : ''}>{label}<input aria-label={`Line ${line.line_number}: ${label}`} className={numeric ? 'amount' : undefined} type={numeric ? 'number' : 'text'} step={numeric ? 'any' : undefined} required={numeric} value={draft.lines[index][key]} onChange={(event) => { setFeedback(''); setDraft((current) => ({ ...current, lines: current.lines.map((fields, position) => position === index ? { ...fields, [key]: event.target.value } : fields) })); }} /></label>)}</div></fieldset>)}</section>
        </fieldset>
        <section className="findings" aria-labelledby="findings-heading"><h3 id="findings-heading">Validation findings ({findings.length})</h3>{findings.length === 0 ? <p className="muted">No findings reported by the API.</p> : <ul>{findings.map((finding, index) => <li key={finding.id ?? index}>
          <div className="finding-heading"><span className={`badge badge--${finding.severity}`}>{statusLabel(finding.severity)}</span><span className="code">{finding.field || 'Field not supplied'}</span>{finding.line_number != null && <span>Line {finding.line_number}</span>}</div><p>{finding.message}</p>
          {finding.confidence != null && <p className="muted">Extraction confidence: {(finding.confidence * 100).toFixed(1)}%</p>}
          {(finding.extracted_value != null || finding.approved_value != null) && <dl className="finding-values"><div><dt>Extracted</dt><dd>{String(finding.extracted_value ?? 'Not supplied')}</dd></div><div><dt>Approved value supplied by API</dt><dd>{String(finding.approved_value ?? 'Not supplied')}</dd></div></dl>}
        </li>)}</ul>}</section>
        {error && <p className="panel panel--error" role="alert">{error} Your unsaved draft is retained.</p>}
        <div className="decision-bar"><div className="actions"><button type="submit" className="button button--secondary" disabled={busy || !dirty}>{patch.isPending ? 'Saving corrections…' : 'Save corrections'}</button><button type="button" className="button button--danger" disabled={busy || dirty} onClick={() => void decide('reject')}>Reject</button><button type="button" className="button button--primary" disabled={busy || dirty} onClick={() => void decide('approve')}>{review.isPending ? 'Recording decision…' : 'Approve invoice'}</button></div><p className="muted">{busy ? 'Wait for the server response before leaving.' : dirty ? 'Decisions are disabled until corrections are saved.' : 'Review decisions use only saved values.'}</p></div>
        <p className={feedback ? 'save-feedback' : 'feedback-placeholder'} role="status" aria-live="polite">{feedback}</p>
      </form>
    </div>
  </section>;
}
