import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import Notice from '@/components/common/Notice';
import { useCreateDmsSystemBatch, useMappingPreview } from '@/hooks/useRegistry';
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
type IntegrationTier = 1 | 2 | 3;
const formatOptions: Array<{
  value: InputFormat;
  label: string;
  detail: string;
  tier: IntegrationTier;
  method: CreateDmsPayload['integration_method'];
}> = [
  { value: 'JSON', label: 'JSON / API', detail: 'Structured payload', tier: 1, method: 'API' },
  { value: 'CSV', label: 'CSV', detail: 'Comma-separated file', tier: 2, method: 'UPLOAD' },
  { value: 'EXCEL', label: 'Excel', detail: '.xlsx and .xls workbooks', tier: 2, method: 'UPLOAD' },
  { value: 'PDF', label: 'PDF', detail: 'Text-based invoice PDF', tier: 3, method: 'UPLOAD' },
];
const tierGroups: Array<{ tier: IntegrationTier; title: string; scope: string; unavailable?: string }> = [
  { tier: 1, title: 'API integration', scope: 'JSON API' },
  { tier: 2, title: 'Structured file integration', scope: 'XML, Excel (.xlsx), and CSV', unavailable: 'XML intake is not enabled yet.' },
  { tier: 3, title: 'Document and legacy intake', scope: 'PDF, email upload, and legacy data', unavailable: 'Email upload and legacy data are not enabled yet.' },
];

type FormatDraft = {
  mapping: SourceMapping;
  sample: string;
};
type PreviewSnapshot = { signature: string; candidate: Record<string, unknown> };

const emptyMapping = (): SourceMapping => ({
  invoice_number: '', invoice_date: '', buyer_oem_id: '', supplier_dealer_code: '',
  currency: '', subtotal: '', tax_amount: '', total_amount: '',
  line_items: {
    source_field: '', description: '', quantity: '', unit_price: '', taxable_amount: '',
    tax_amount: '', line_total: '', item_code: '', chassis_number: '', item_category: '',
    discount_amount: '', tax_rate: '',
  },
});

const initialDrafts = (): Record<InputFormat, FormatDraft> => ({
  JSON: { mapping: emptyMapping(), sample: serialize(jsonDemoSource) },
  CSV: { mapping: emptyMapping(), sample: serialize(csvDemoSource) },
  EXCEL: { mapping: emptyMapping(), sample: serialize(csvDemoSource) },
  PDF: { mapping: emptyMapping(), sample: serialize(jsonDemoSource) },
});

const formatLabel = (format: InputFormat) => formatOptions.find((option) => option.value === format)?.label ?? format;
const formatConfig = (format: InputFormat) => formatOptions.find((option) => option.value === format)!;

export default function DmsOnboardingPage() {
  const [name, setName] = useState('');
  const [multipleFormats, setMultipleFormats] = useState(false);
  const [selectedFormats, setSelectedFormats] = useState<InputFormat[]>(['JSON']);
  const [activeFormat, setActiveFormat] = useState<InputFormat>('JSON');
  const [drafts, setDrafts] = useState<Record<InputFormat, FormatDraft>>(initialDrafts);
  const [previews, setPreviews] = useState<Partial<Record<InputFormat, PreviewSnapshot>>>({});
  const [localError, setLocalError] = useState('');
  const preview = useMappingPreview();
  const create = useCreateDmsSystemBatch();
  const draft = drafts[activeFormat];
  const structured = activeFormat !== 'PDF';
  const signature = serialize({ mapping: draft.mapping, sample: draft.sample });
  const activePreview = previews[activeFormat];
  const allMappingsPreviewed = selectedFormats.every((format) =>
    format === 'PDF' || previews[format]?.signature === serialize({ mapping: drafts[format].mapping, sample: drafts[format].sample }),
  );
  const busy = preview.isPending || create.isPending;
  const updateDraft = (format: InputFormat, updates: Partial<FormatDraft>) => {
    setDrafts((current) => ({ ...current, [format]: { ...current[format], ...updates } }));
    setLocalError('');
  };
  const changeFormatSelection = (format: InputFormat) => {
    if (!multipleFormats) {
      setSelectedFormats([format]);
      setActiveFormat(format);
      return;
    }
    if (selectedFormats.includes(format)) {
      if (selectedFormats.length === 1) return;
      const next = selectedFormats.filter((item) => item !== format);
      setSelectedFormats(next);
      if (activeFormat === format) setActiveFormat(next[0]);
      return;
    }
    setSelectedFormats([...selectedFormats, format]);
    setActiveFormat(format);
  };
  const cleanMapping = (source: SourceMapping): SourceMapping => {
    const clean = (entries: Record<string, unknown>) => Object.fromEntries(Object.entries(entries)
      .filter(([key, value]) => !optionalFields.has(key) || String(value).trim() !== '')
      .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value]));
    return { ...clean(source as unknown as Record<string, unknown>), line_items: clean(source.line_items) } as unknown as SourceMapping;
  };
  const hasRequiredPaths = (mapping: SourceMapping) => {
    const headerPaths = Object.keys(headerLabels)
      .filter((key) => !optionalFields.has(key))
      .map((key) => (mapping as unknown as Record<string, unknown>)[key]);
    const linePaths = Object.keys(lineLabels)
      .filter((key) => !optionalFields.has(key))
      .map((key) => (mapping.line_items as unknown as Record<string, unknown>)[key]);
    return [...headerPaths, ...linePaths].every((path) => typeof path === 'string' && path.trim());
  };
  const runPreview = async () => {
    if (busy || !structured || USE_DEV_MOCK_API) return;
    setLocalError('');
    if (!hasRequiredPaths(draft.mapping)) {
      setLocalError('Enter every required source path before previewing the mapping.');
      return;
    }
    try {
      const payload: unknown = JSON.parse(draft.sample);
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('Sample data must be a source object, not a list or scalar.');
      const result = await preview.mutateAsync({ mapping_config: cleanMapping(draft.mapping), payload: payload as Record<string, unknown> });
      setPreviews((current) => ({ ...current, [activeFormat]: { signature, candidate: result.canonical_candidate } }));
    } catch (error) {
      setLocalError(error instanceof SyntaxError ? 'Sample JSON is malformed. Correct its syntax before previewing.' : error instanceof Error ? error.message : 'Mapping preview failed.');
    }
  };
  const fillMockData = () => {
    setName('Demo DMS');
    setDrafts((current) => {
      const next = { ...current };
      selectedFormats.forEach((format) => {
        const isJson = format === 'JSON';
        next[format] = {
          mapping: format === 'PDF' ? emptyMapping() : isJson ? jsonDemoMapping : csvDemoMapping,
          sample: serialize(isJson ? jsonDemoSource : csvDemoSource),
        };
      });
      return next;
    });
    setPreviews((current) => {
      const next = { ...current };
      selectedFormats.forEach((format) => { delete next[format]; });
      return next;
    });
    setLocalError('');
    preview.reset();
    create.reset();
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || create.isSuccess || USE_DEV_MOCK_API || !allMappingsPreviewed || !name.trim()) return;
    setLocalError('');
    try {
      await create.mutateAsync({ profiles: selectedFormats.map((format) => {
        const profile = drafts[format];
        const config = formatConfig(format);
        return {
          name: name.trim(),
          integration_tier: config.tier,
          integration_method: config.method,
          input_format: format,
          ...(format !== 'PDF' ? { mapping_config: cleanMapping(profile.mapping) } : {}),
        };
      }) });
    } catch { /* Typed mutation error is shown below. */ }
  };

  const mappingRows = (line: boolean) => Object.entries(line ? lineLabels : headerLabels).map(([key, label]) => {
    const values = line ? draft.mapping.line_items : draft.mapping;
    const hints = line
      ? (activeFormat === 'JSON' ? jsonDemoMapping.line_items : csvDemoMapping.line_items)
      : (activeFormat === 'JSON' ? jsonDemoMapping : csvDemoMapping);
    const value = (values as unknown as Record<string, unknown>)[key];
    const hint = (hints as unknown as Record<string, unknown>)[key];
    return <label className="mapping-row" key={key}>
      <span><strong>{label}</strong><span className="code">{line && key !== 'source_field' ? 'line_items.' : ''}{key}</span><span className="muted">{optionalFields.has(key) ? 'Optional' : 'Required'}</span></span>
      <input aria-label={`${line ? 'Line' : 'Header'} ${label} source path`} required={!optionalFields.has(key)} value={typeof value === 'string' ? value : ''} placeholder={typeof hint === 'string' ? hint : 'Source field path'} onChange={(event) => {
        const nextMapping = line
          ? { ...draft.mapping, line_items: { ...draft.mapping.line_items, [key]: event.target.value } }
          : { ...draft.mapping, [key]: event.target.value };
        updateDraft(activeFormat, { mapping: nextMapping as SourceMapping });
      }} autoCapitalize="none" spellCheck={false} />
    </label>;
  });

  const resetForm = () => {
    create.reset();
    preview.reset();
    setName('');
    setMultipleFormats(false);
    setSelectedFormats(['JSON']);
    setActiveFormat('JSON');
    setDrafts(initialDrafts());
    setPreviews({});
    setLocalError('');
  };

  return <section className="view onboarding-view">
    <header className="view__header"><div><p className="orientation">Dealer integrations / Registry</p><h1>Register a DMS</h1><p className="muted">Choose invoice formats and map each source to OneDMS canonical fields.</p></div><Link className="button button--secondary" to="/documents/new">Open intake</Link></header>
    {USE_DEV_MOCK_API && <Notice>Development fixture mode: registry creation and server preview are unavailable. Switch to the live API to register profiles.</Notice>}
    {create.isSuccess ? <section className="panel stack"><header><h2>DMS profiles registered</h2><p className="muted">Each format has its own integration profile and source mapping.</p></header><ul className="registered-profile-list">{create.data.profiles.map((profile) => <li key={profile.id}><div><strong>{profile.name}</strong><span className="muted">{formatLabel(profile.input_format)} profile, ID #{profile.id}{profile.active_mapping_version != null ? `, mapping version ${profile.active_mapping_version}` : ''}</span></div><Link className="button button--secondary" to={`/documents/new?dms_id=${profile.id}`}>Use profile for intake</Link></li>)}</ul><button className="button button--primary" onClick={resetForm}>Register another DMS</button></section> :
    <form className="stack onboarding-form" onSubmit={(event) => void submit(event)}>
      <fieldset disabled={busy} className="stack"><legend className="sr-only">DMS format and mapping configuration</legend>
        <section className="profile-metadata"><header><h2>DMS details</h2><p className="muted">Profiles share this DMS name. No credentials or live connector are configured here.</p><button type="button" className="button button--secondary" onClick={fillMockData}>Fill selected profiles with mock data</button></header><div className="metadata-grid">
          <label>DMS name<input required maxLength={255} value={name} placeholder="e.g. Dealer billing system" onChange={(event) => { setName(event.target.value); setLocalError(''); }} /></label>
        </div></section>
        <fieldset className="format-plan"><legend>Will invoice data arrive in multiple formats?</legend><div className="format-plan__choices">
          <label><input type="radio" name="multiple-formats" checked={!multipleFormats} onChange={() => { setMultipleFormats(false); if (selectedFormats.length > 1) { setSelectedFormats([activeFormat]); } }} /><span><strong>No, one format</strong><small>Register one profile</small></span></label>
          <label><input type="radio" name="multiple-formats" checked={multipleFormats} onChange={() => setMultipleFormats(true)} /><span><strong>Yes, multiple formats</strong><small>Register a profile for each</small></span></label>
        </div></fieldset>
        <fieldset className="format-selector"><legend>{multipleFormats ? 'Select every format this DMS sends' : 'Select the format this DMS sends'}</legend><div className="tier-groups">
          {tierGroups.map((group) => <section className="tier-group" key={group.tier}>
            <header><h3>Tier {group.tier}: {group.title}</h3><p className="muted">{group.scope}</p></header>
            <div className="format-choices">
              {formatOptions.filter((option) => option.tier === group.tier).map((option) => <label className={selectedFormats.includes(option.value) ? 'format-choice format-choice--selected' : 'format-choice'} key={option.value}>
                <input type={multipleFormats ? 'checkbox' : 'radio'} name="input-format" checked={selectedFormats.includes(option.value)} onChange={() => changeFormatSelection(option.value)} />
                <span><strong>{option.label}</strong><small>{option.detail}</small></span>
              </label>)}
            </div>
            {group.unavailable && <p className="tier-group__unavailable">Not available yet: {group.unavailable}</p>}
          </section>)}
        </div></fieldset>
        <div className="profile-tabs" role="tablist" aria-label="Format profiles">
          {selectedFormats.map((format) => <button type="button" role="tab" aria-selected={activeFormat === format} className={activeFormat === format ? 'profile-tab profile-tab--active' : 'profile-tab'} key={format} onClick={() => setActiveFormat(format)}>{formatLabel(format)}</button>)}
        </div>
        <section className="profile-settings"><header><h2>{formatLabel(activeFormat)} profile</h2><p className="muted">This profile receives only {formatLabel(activeFormat)} invoices and owns its mapping.</p></header><div className="profile-route-facts">
          <div><span>Integration tier</span><strong>Tier {formatConfig(activeFormat).tier}</strong></div>
          <div><span>Integration method</span><strong>{formatConfig(activeFormat).method === 'API' ? 'API' : 'File upload'}</strong></div>
        </div></section>
        {structured ? <>
          <Notice>{activeFormat === 'JSON' ? <>The parser reads structured JSON. Map its exact source fields to canonical invoice fields; no AI inference or field discovery is used.</> : <>The parser reads the first worksheet or CSV header row. Map header fields from the first line and invoice line fields from <span className="code">rows</span>.</>}</Notice>
          <div className="mapping-workbench">
            <section className="mapping-editor stack"><header><h2>Source mapping</h2><p className="muted">Canonical fields on the left; source paths on the right. Dotted paths support nested JSON values.</p></header>
              <section><h3>Invoice header</h3><div className="mapping-rows">{mappingRows(false)}</div></section>
              <section><h3>Invoice lines</h3><p className="muted">The line array path starts at the source root. Remaining paths are relative to each row.</p><div className="mapping-rows">{mappingRows(true)}</div></section>
            </section>
            <section className="sample-editor stack"><header><h2>{activeFormat === 'JSON' ? 'Source JSON sample' : `${formatLabel(activeFormat)} mapping sample`}</h2><p className="muted">Edit this example to match the selected DMS profile before previewing.</p></header>
              <label>Sample data<textarea rows={18} value={draft.sample} onChange={(event) => updateDraft(activeFormat, { sample: event.target.value })} spellCheck={false} /></label>
              <div className="actions"><button type="button" className="button button--primary" disabled={busy || USE_DEV_MOCK_API} onClick={() => void runPreview()}>{preview.isPending ? 'Previewing…' : 'Preview mapping'}</button><button type="button" className="button button--secondary" onClick={() => {
                updateDraft(activeFormat, { mapping: emptyMapping(), sample: serialize(activeFormat === 'JSON' ? jsonDemoSource : csvDemoSource) });
                setPreviews((current) => { const next = { ...current }; delete next[activeFormat]; return next; });
              }}>Reset sample and mapping</button></div>
              <p className="muted">Preview verifies the current sample against this mapping. It does not approve invoices or guarantee unseen layouts.</p>
              {activePreview && activePreview.signature === signature ? <><Notice kind="success">Server mapping preview passed.</Notice><h3>Canonical preview</h3><pre className="source-text" tabIndex={0} aria-label="Server canonical mapping preview">{serialize(activePreview.candidate)}</pre></> : <Notice>A successful preview is required for this format before registration.</Notice>}
            </section>
          </div>
        </> : <section className="pdf-profile-note"><h3>PDF parser</h3><p>PDF profiles use the existing local text and table parser. A mapping preview is not required. Scanned image-only PDFs and unfamiliar layouts may need a different extraction path or reviewer correction.</p></section>}
        <section className="registration-bar"><div><strong>{selectedFormats.length} profile{selectedFormats.length === 1 ? '' : 's'} to register</strong><p className="muted">{selectedFormats.map(formatLabel).join(', ')}</p></div><button type="submit" className="button button--primary" disabled={busy || USE_DEV_MOCK_API || !name.trim() || !allMappingsPreviewed}>{create.isPending ? 'Registering profiles…' : 'Register DMS profiles'}</button></section>
      </fieldset>
      {(localError || create.isError) && <Notice kind="error">{localError || create.error?.message}</Notice>}
    </form>}
  </section>;
}