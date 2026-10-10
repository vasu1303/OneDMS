import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import Notice from '@/components/common/Notice';
import { useCreateDmsSystem, useMappingPreview } from '@/hooks/useRegistry';
import { csvDemoMapping, csvDemoSource, jsonDemoMapping, jsonDemoSource } from '@/constants/integrationDemo';
import { USE_DEV_MOCK_API } from '@/services/api';
import type { CreateDmsPayload, InputFormat, SourceMapping } from '@/types';

const headerLabels: Record<string, string> = {
  invoice_number: 'Invoice number', invoice_date: 'Invoice date', buyer_oem_id: 'Buyer OEM code',
  supplier_dealer_code: 'Supplier dealer code', currency: 'Currency', subtotal: 'Subtotal',
  tax_amount: 'Tax total', total_amount: 'Grand total',
};
const lineLabels: Record<string, string> = {
  source_field: 'Line array path (from source root)', item_code: 'Item code', description: 'Description',
  quantity: 'Quantity', unit_price: 'Unit price', discount_amount: 'Discount', taxable_amount: 'Taxable amount',
  tax_rate: 'Tax rate', tax_amount: 'Tax amount', line_total: 'Line total', chassis_number: 'Chassis number', item_category: 'Item category',
};
const optionalFields = new Set(['supplier_dealer_code', 'item_code', 'discount_amount', 'tax_rate', 'chassis_number', 'item_category']);
const serialize = (source: unknown) => JSON.stringify(source, null, 2);

export default function DmsOnboardingPage() {
  const [name, setName] = useState('');
  const [tier, setTier] = useState(1);
  const [method, setMethod] = useState<CreateDmsPayload['integration_method']>('API');
  const [format, setFormat] = useState<InputFormat>('JSON');
  const [mapping, setMapping] = useState<SourceMapping>(jsonDemoMapping);
  const [sample, setSample] = useState(serialize(jsonDemoSource));
  const [previewSignature, setPreviewSignature] = useState('');
  const [localError, setLocalError] = useState('');
  const preview = useMappingPreview();
  const create = useCreateDmsSystem();
  const signature = serialize({ name, tier, method, format, mapping, sample });
  const previewValid = preview.isSuccess && previewSignature === signature;
  const structured = format !== 'PDF';
  const busy = preview.isPending || create.isPending;
  const invalidate = () => { setPreviewSignature(''); setLocalError(''); preview.reset(); create.reset(); };

  const changeFormat = (next: InputFormat) => {
    invalidate(); setFormat(next);
    setMapping(next === 'CSV' ? csvDemoMapping : jsonDemoMapping);
    setSample(serialize(next === 'CSV' ? csvDemoSource : jsonDemoSource));
    setMethod(next === 'JSON' ? 'API' : 'UPLOAD');
  };

  const changePath = (key: string, value: string, line: boolean) => {
    invalidate();
    setMapping((current) => line ? { ...current, line_items: { ...current.line_items, [key]: value } } : { ...current, [key]: value });
  };
  const cleanMapping = (): SourceMapping => {
    // Empty optional rows mean “not mapped”; required rows are validated by the server.
    const clean = (entries: Record<string, unknown>) => Object.fromEntries(Object.entries(entries)
      .filter(([key, value]) => !optionalFields.has(key) || String(value).trim() !== '')
      .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value]));
    return { ...clean(mapping as unknown as Record<string, unknown>), line_items: clean(mapping.line_items) } as unknown as SourceMapping;
  };
  const runPreview = async () => {
    if (busy || !structured || USE_DEV_MOCK_API) return;
    setLocalError(''); setPreviewSignature('');
    try {
      const payload: unknown = JSON.parse(sample);
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('Sample JSON must be a source object, not a list or scalar.');
      await preview.mutateAsync({ mapping_config: cleanMapping(), payload: payload as Record<string, unknown> });
      setPreviewSignature(signature);
    } catch (error) {
      setLocalError(error instanceof SyntaxError ? 'Sample JSON is malformed. Correct its syntax before previewing.' : error instanceof Error ? error.message : 'Mapping preview failed.');
    }
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || create.isSuccess || USE_DEV_MOCK_API || (structured && !previewValid)) return;
    setLocalError('');
    try {
      await create.mutateAsync({ name: name.trim(), integration_tier: tier, integration_method: method,
        input_format: format, ...(structured ? { mapping_config: cleanMapping() } : {}) });
    } catch { /* Typed mutation error is shown below. */ }
  };

  const mappingRows = (line: boolean) => Object.entries(line ? lineLabels : headerLabels).map(([key, label]) => {
    const values = line ? mapping.line_items : mapping;
    const value = (values as unknown as Record<string, unknown>)[key];
    return <label className="mapping-row" key={key}>
      <span><strong>{label}</strong><span className="code">{line && key !== 'source_field' ? 'line_items.' : ''}{key}</span><span className="muted">{optionalFields.has(key) ? 'Optional' : 'Required'}</span></span>
      <input aria-label={`${line ? 'Line' : 'Header'} ${label} source path`} required={!optionalFields.has(key)} value={typeof value === 'string' ? value : ''} onChange={(event) => changePath(key, event.target.value, line)} placeholder="Source field path" autoCapitalize="none" spellCheck={false} />
    </label>;
  });

  return <section className="view onboarding-view">
    <header className="view__header"><div><p className="orientation">Dealer integrations / Registry</p><h1>Create DMS integration profile</h1><p className="muted">Register a source system and explicitly map its field names to the canonical invoice.</p></div><Link className="button button--secondary" to="/documents/new">Open intake</Link></header>
    {USE_DEV_MOCK_API && <Notice>Development fixture mode: registry creation and server preview are unsupported. Switch to the live API to register a profile.</Notice>}
    {create.isSuccess ? <section className="panel stack"><h2>Profile registered</h2><Notice kind="success">{create.data.name} · DMS ID #{create.data.id} · {create.data.input_format}{create.data.active_mapping_version != null ? ` · Mapping v${create.data.active_mapping_version}` : ''}</Notice><p>The server has saved this integration profile. Select a registered dealer in intake to submit its first invoice.</p><div className="actions"><Link className="button button--primary" to={`/documents/new?dms_id=${create.data.id}`}>Use this profile in intake</Link><button className="button button--secondary" onClick={() => { invalidate(); setName(''); }}>Create another profile</button></div></section> :
    <form className="stack" onSubmit={(event) => void submit(event)}>
      <fieldset disabled={busy} className="stack"><legend className="sr-only">Integration profile configuration</legend>
        <section className="profile-metadata"><header><h2>Source system</h2><p className="muted">Profile metadata, not credentials or a live connector.</p></header><div className="metadata-grid">
          <label>Profile name<input required maxLength={255} value={name} placeholder="e.g. Dealer billing JSON" onChange={(event) => { invalidate(); setName(event.target.value); }} /></label>
          <label>Integration tier<select value={tier} onChange={(event) => { invalidate(); setTier(Number(event.target.value)); }}><option value={1}>Tier 1</option><option value={2}>Tier 2</option><option value={3}>Tier 3</option></select></label>
          <label>Input format<select value={format} onChange={(event) => changeFormat(event.target.value as InputFormat)}><option>JSON</option><option>CSV</option><option>PDF</option></select></label>
          <label>Integration method<select value={method} onChange={(event) => { invalidate(); setMethod(event.target.value as CreateDmsPayload['integration_method']); }}><option value="API">API</option><option value="UPLOAD">Upload</option></select></label>
        </div></section>
        {structured ? <>
          <Notice>{format === 'JSON' ? <><strong>Explicit alias mapping:</strong> the demo maps source <span className="code">billNo</span> to canonical <span className="code">invoice_number</span>. No AI inference or automatic field discovery is used.</> : <><strong>CSV demo limitation:</strong> intake currently adapts a fixed demo column layout into a JSON wrapper. Preview below tests that wrapper, not a CSV parser. Registering a mapping does not add support for unseen CSV layouts.</>}</Notice>
          <div className="mapping-workbench">
            <section className="mapping-editor stack"><header><h2>Field alias mapping</h2><p className="muted">Canonical field on the left; source path on the right. Use dotted paths for nested objects.</p></header>
              <section><h3>Invoice header</h3><div className="mapping-rows">{mappingRows(false)}</div></section>
              <section><h3>Invoice lines</h3><p className="muted">Array path starts at the source root. Other line paths are relative to each array item.</p><div className="mapping-rows">{mappingRows(true)}</div></section>
            </section>
            <section className="sample-editor stack"><header><h2>{format === 'CSV' ? 'CSV adapter output sample' : 'Source JSON sample'}</h2><p className="muted">Synthetic invoice · subtotal 1,000 + tax 180 = total 1,180. Adjust the dealer code to your registered dealer before intake.</p></header>
              <label>Editable sample JSON<textarea rows={24} value={sample} onChange={(event) => { invalidate(); setSample(event.target.value); }} spellCheck={false} /></label>
              <div className="actions"><button type="button" className="button button--primary" disabled={busy || USE_DEV_MOCK_API} onClick={() => void runPreview()}>{preview.isPending ? 'Previewing on server…' : 'Preview mapping on server'}</button><button type="button" className="button button--secondary" onClick={() => { invalidate(); setMapping(format === 'CSV' ? csvDemoMapping : jsonDemoMapping); setSample(serialize(format === 'CSV' ? csvDemoSource : jsonDemoSource)); }}>Reset demo mapping & sample</button></div>
              <p className="muted">The API applies these exact paths. A successful preview checks this sample; it is not invoice approval or a guarantee for future payloads.</p>
              {previewValid ? <><Notice kind="success">Server preview succeeded. This configuration can now be registered.</Notice><h3>Canonical candidate · server result</h3><pre className="source-text" tabIndex={0} aria-label="Server canonical mapping preview">{serialize(preview.data?.canonical_candidate)}</pre></> : <Notice>Preview required. Editing metadata, mapping, format, or sample invalidates the previous preview.</Notice>}
            </section>
          </div>
        </> : <section className="panel stack"><h2>PDF layout parser</h2><Notice>No field alias mapping is stored for PDF. Processing uses the existing layout parser; registering this profile does not train a new parser or enable arbitrary PDF layouts.</Notice><p className="muted">Submit a supported layout, inspect the extracted invoice, and resolve validation findings before approval.</p></section>}
        <div className="registration-bar"><p className="muted">{structured ? previewValid ? 'Preview verified for the current configuration.' : 'Run a successful server preview before registration.' : 'PDF profile registration does not require a mapping preview.'}</p><button type="submit" className="button button--primary" disabled={busy || USE_DEV_MOCK_API || !name.trim() || (structured && !previewValid)}>{create.isPending ? 'Registering…' : 'Create integration profile'}</button></div>
      </fieldset>
      {(localError || create.isError) && <Notice kind="error">{localError || create.error?.message}</Notice>}
    </form>}
  </section>;
}