import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import Notice from '@/components/common/Notice';
import { useCreateDmsSystemBatch, useMappingPreview } from '@/hooks/useRegistry';
import { csvDemoMapping, csvDemoSource, jsonDemoMapping, jsonDemoSource } from '@/constants/integrationDemo';
import { USE_DEV_MOCK_API } from '@/services/api';
import type { CreateDmsPayload, InputFormat, SourceMapping } from '@/types';

const headerLabels: Record<string, string> = {
  invoice_number: 'Invoice number',
  invoice_date: 'Invoice date',
  buyer_oem_id: 'Buyer OEM code',
  supplier_dealer_code: 'Supplier dealer code',
  currency: 'Currency',
  subtotal: 'Subtotal',
  tax_amount: 'Tax total',
  total_amount: 'Grand total',
};

const lineLabels: Record<string, string> = {
  source_field: 'Line array path (from source root)',
  item_code: 'Item code',
  description: 'Description',
  quantity: 'Quantity',
  unit_price: 'Unit price',
  discount_amount: 'Discount',
  taxable_amount: 'Taxable amount',
  tax_rate: 'Tax rate',
  tax_amount: 'Tax amount',
  line_total: 'Line total',
  chassis_number: 'Chassis number',
  item_category: 'Item category',
};

const optionalFields = new Set([
  'supplier_dealer_code',
  'item_code',
  'discount_amount',
  'tax_rate',
  'chassis_number',
  'item_category',
]);

const serialize = (source: unknown) => JSON.stringify(source, null, 2);

type IntegrationTier = 1 | 2 | 3;

const formatOptions: Array<{
  value: InputFormat;
  label: string;
  badge: string;
  detail: string;
  tier: IntegrationTier;
  method: CreateDmsPayload['integration_method'];
}> = [
  { value: 'JSON', label: 'JSON / REST API', badge: 'JSON', detail: 'Real-time structured API payload', tier: 1, method: 'API' },
  { value: 'CSV', label: 'CSV Flatfile', badge: 'CSV', detail: 'Comma-separated batch data export', tier: 2, method: 'UPLOAD' },
  { value: 'EXCEL', label: 'Excel Workbook', badge: 'XLSX', detail: 'Microsoft Excel .xlsx / .xls sheets', tier: 2, method: 'UPLOAD' },
  { value: 'PDF', label: 'Digital PDF', badge: 'PDF', detail: 'Visual invoice documents & layouts', tier: 3, method: 'UPLOAD' },
];

const tierGroups: Array<{ tier: IntegrationTier; title: string; scope: string; badge: string; unavailable?: string }> = [
  { tier: 1, title: 'Tier 1: Direct API Streaming', scope: 'Real-time JSON payload feed over HTTPS / Webhook', badge: 'Direct API' },
  { tier: 2, title: 'Tier 2: Structured Files', scope: 'Standard delimited files and workbooks (CSV, XLSX)', badge: 'Structured Batch' },
  { tier: 3, title: 'Tier 3: Document Parser', scope: 'OCR & automated table extraction from PDF documents', badge: 'Document Intake' },
];

type FormatDraft = {
  mapping: SourceMapping;
  sample: string;
};

type PreviewSnapshot = { signature: string; candidate: Record<string, unknown> };

const emptyMapping = (): SourceMapping => ({
  invoice_number: '',
  invoice_date: '',
  buyer_oem_id: '',
  supplier_dealer_code: '',
  currency: '',
  subtotal: '',
  tax_amount: '',
  total_amount: '',
  line_items: {
    source_field: '',
    description: '',
    quantity: '',
    unit_price: '',
    taxable_amount: '',
    tax_amount: '',
    line_total: '',
    item_code: '',
    chassis_number: '',
    item_category: '',
    discount_amount: '',
    tax_rate: '',
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
    const clean = (entries: Record<string, unknown>) =>
      Object.fromEntries(
        Object.entries(entries)
          .filter(([key, value]) => !optionalFields.has(key) || String(value).trim() !== '')
          .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value]),
      );
    return {
      ...clean(source as unknown as Record<string, unknown>),
      line_items: clean(source.line_items),
    } as unknown as SourceMapping;
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
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        throw new Error('Sample data must be a source object, not a list or scalar.');
      }
      const result = await preview.mutateAsync({
        mapping_config: cleanMapping(draft.mapping),
        payload: payload as Record<string, unknown>,
      });
      setPreviews((current) => ({ ...current, [activeFormat]: { signature, candidate: result.canonical_candidate } }));
    } catch (error) {
      setLocalError(
        error instanceof SyntaxError
          ? 'Sample JSON is malformed. Correct its syntax before previewing.'
          : error instanceof Error
            ? error.message
            : 'Mapping preview failed.',
      );
    }
  };

  const fillMockData = () => {
    setName('Reynolds & Reynolds ERA-IGNITE');
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
      selectedFormats.forEach((format) => {
        delete next[format];
      });
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
      await create.mutateAsync({
        profiles: selectedFormats.map((format) => {
          const profile = drafts[format];
          const config = formatConfig(format);
          return {
            name: name.trim(),
            integration_tier: config.tier,
            integration_method: config.method,
            input_format: format,
            ...(format !== 'PDF' ? { mapping_config: cleanMapping(profile.mapping) } : {}),
          };
        }),
      });
    } catch {
      /* Mutation error displayed below */
    }
  };

  const mappingRows = (line: boolean) =>
    Object.entries(line ? lineLabels : headerLabels).map(([key, label]) => {
      const values = line ? draft.mapping.line_items : draft.mapping;
      const hints = line
        ? activeFormat === 'JSON'
          ? jsonDemoMapping.line_items
          : csvDemoMapping.line_items
        : activeFormat === 'JSON'
          ? jsonDemoMapping
          : csvDemoMapping;
      const value = (values as unknown as Record<string, unknown>)[key];
      const hint = (hints as unknown as Record<string, unknown>)[key];
      const isOptional = optionalFields.has(key);

      return (
        <div className="onboarding-mapping-item" key={key}>
          <div className="onboarding-mapping-meta">
            <span className="onboarding-mapping-label">{label}</span>
            <code className="onboarding-mapping-code">
              {line && key !== 'source_field' ? 'line_items.' : ''}
              {key}
            </code>
            <span className={`onboarding-pill ${isOptional ? 'onboarding-pill--optional' : 'onboarding-pill--required'}`}>
              {isOptional ? 'Optional' : 'Required'}
            </span>
          </div>
          <div className="onboarding-mapping-input-wrap">
            <input
              aria-label={`${line ? 'Line' : 'Header'} ${label} source path`}
              required={!isOptional}
              value={typeof value === 'string' ? value : ''}
              placeholder={typeof hint === 'string' ? `e.g. ${hint}` : 'Source field path'}
              onChange={(event) => {
                const nextMapping = line
                  ? { ...draft.mapping, line_items: { ...draft.mapping.line_items, [key]: event.target.value } }
                  : { ...draft.mapping, [key]: event.target.value };
                updateDraft(activeFormat, { mapping: nextMapping as SourceMapping });
              }}
              autoCapitalize="none"
              spellCheck={false}
              className="onboarding-input code-font"
            />
          </div>
        </div>
      );
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

  return (
    <section className="view onboarding-view">
      {/* Page Header */}
      <header className="view__header">
        <div>
          <div className="view__eyebrow">
            <span>DMS SYSTEM REGISTRY</span>
          </div>
          <h1>Register & Configure DMS</h1>
          <p className="muted">
            Configure dealership DMS integration profiles, source format bindings, and canonical schema mappings.
          </p>
        </div>
        <div className="view__header-actions">
          <Link to="/documents/new" className="button button--secondary">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="12" y1="18" x2="12" y2="12" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
            <span>Open Intake</span>
          </Link>
        </div>
      </header>

      {USE_DEV_MOCK_API && (
        <Notice>
          Development fixture mode: registry creation and server preview are unavailable. Switch to backend mode to register profiles.
        </Notice>
      )}

      {create.isSuccess ? (
        /* Success State */
        <div className="onboarding-card onboarding-success-card">
          <div className="onboarding-success-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <h2>DMS Profiles Successfully Registered</h2>
          <p className="muted">
            {create.data.profiles.length} profile{create.data.profiles.length === 1 ? '' : 's'} registered under &ldquo;{name}&rdquo;. Each format now possesses an active canonical routing configuration.
          </p>

          <div className="onboarding-registered-grid">
            {create.data.profiles.map((profile) => (
              <div className="onboarding-registered-item" key={profile.id}>
                <div className="onboarding-registered-item__header">
                  <span className={`format-tag format-tag--${profile.input_format.toLowerCase()}`}>
                    {profile.input_format}
                  </span>
                  <span className="onboarding-registered-id">Profile ID #{profile.id}</span>
                </div>
                <div className="onboarding-registered-item__body">
                  <strong>{profile.name}</strong>
                  <p className="muted">
                    {formatLabel(profile.input_format)}
                    {profile.active_mapping_version != null ? ` · Mapping v${profile.active_mapping_version}` : ' · Standard parser'}
                  </p>
                </div>
                <Link className="button button--primary button--sm" to={`/documents/new?dms_id=${profile.id}`}>
                  Use for Intake
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </Link>
              </div>
            ))}
          </div>

          <div className="onboarding-success-actions">
            <button type="button" className="button button--secondary" onClick={resetForm}>
              Register Another DMS
            </button>
            <Link to="/documents" className="button button--primary">
              View Document Queue
            </Link>
          </div>
        </div>
      ) : (
        /* Multi-Step Onboarding Form */
        <form className="onboarding-form" onSubmit={(event) => void submit(event)}>
          <fieldset disabled={busy} className="onboarding-fieldset">
            {/* Step 1: System Identity */}
            <div className="onboarding-card">
              <div className="onboarding-card__header">
                <div className="onboarding-card__title-wrap">
                  <div className="onboarding-step-badge">STEP 1 OF 3</div>
                  <h2>DMS System Identity</h2>
                  <p className="muted">Specify the software system or dealer management provider name.</p>
                </div>
                <button type="button" className="button button--secondary button--sm" onClick={fillMockData}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                  </svg>
                  <span>Fill Demo Sample</span>
                </button>
              </div>

              <div className="onboarding-card__content">
                <div className="onboarding-form-group">
                  <label htmlFor="dms-name-input" className="onboarding-label">
                    DMS Platform Name <span className="text-danger">*</span>
                  </label>
                  <input
                    id="dms-name-input"
                    required
                    maxLength={255}
                    value={name}
                    placeholder="e.g. Reynolds & Reynolds ERA-IGNITE, CDK Drive, Dealertrack DMS"
                    onChange={(event) => {
                      setName(event.target.value);
                      setLocalError('');
                    }}
                    className="onboarding-input"
                  />
                  <small className="muted">
                    Profiles will be registered under this system name. Dealer endpoints will attach to these profiles.
                  </small>
                </div>

                <div className="onboarding-form-group">
                  <label className="onboarding-label">Format Architecture</label>
                  <div className="onboarding-toggle-grid">
                    <label className={`onboarding-toggle-card ${!multipleFormats ? 'onboarding-toggle-card--selected' : ''}`}>
                      <input
                        type="radio"
                        name="multiple-formats"
                        checked={!multipleFormats}
                        onChange={() => {
                          setMultipleFormats(false);
                          if (selectedFormats.length > 1) {
                            setSelectedFormats([activeFormat]);
                          }
                        }}
                      />
                      <div className="onboarding-toggle-card__body">
                        <div className="onboarding-toggle-card__header">
                          <span className="onboarding-toggle-radio"></span>
                          <strong>Single Format System</strong>
                        </div>
                        <p className="muted">This DMS emits invoices in one uniform format (e.g. only JSON API or only CSV).</p>
                      </div>
                    </label>

                    <label className={`onboarding-toggle-card ${multipleFormats ? 'onboarding-toggle-card--selected' : ''}`}>
                      <input
                        type="radio"
                        name="multiple-formats"
                        checked={multipleFormats}
                        onChange={() => setMultipleFormats(true)}
                      />
                      <div className="onboarding-toggle-card__body">
                        <div className="onboarding-toggle-card__header">
                          <span className="onboarding-toggle-radio"></span>
                          <strong>Multi-Format DMS Group</strong>
                        </div>
                        <p className="muted">Register multiple integration profiles (e.g. JSON API + CSV export + PDF fallback).</p>
                      </div>
                    </label>
                  </div>
                </div>
              </div>
            </div>

            {/* Step 2: Format Selection & Ingestion Tiers */}
            <div className="onboarding-card">
              <div className="onboarding-card__header">
                <div className="onboarding-card__title-wrap">
                  <div className="onboarding-step-badge">STEP 2 OF 3</div>
                  <h2>Supported Invoice Formats</h2>
                  <p className="muted">
                    {multipleFormats
                      ? 'Select every format this DMS will transmit to the OneDMS platform.'
                      : 'Select the primary format this DMS will transmit.'}
                  </p>
                </div>
              </div>

              <div className="onboarding-card__content">
                <div className="onboarding-tiers-list">
                  {tierGroups.map((group) => (
                    <div className="onboarding-tier-section" key={group.tier}>
                      <div className="onboarding-tier-header">
                        <span className="onboarding-tier-tag">{group.badge}</span>
                        <div>
                          <strong>{group.title}</strong>
                          <span className="muted"> — {group.scope}</span>
                        </div>
                      </div>

                      <div className="onboarding-format-cards">
                        {formatOptions
                          .filter((option) => option.tier === group.tier)
                          .map((option) => {
                            const isSelected = selectedFormats.includes(option.value);
                            return (
                              <label
                                className={`onboarding-format-option ${isSelected ? 'onboarding-format-option--selected' : ''}`}
                                key={option.value}
                              >
                                <input
                                  type={multipleFormats ? 'checkbox' : 'radio'}
                                  name="input-format"
                                  checked={isSelected}
                                  onChange={() => changeFormatSelection(option.value)}
                                />
                                <div className="onboarding-format-option__left">
                                  <span className={`format-tag format-tag--${option.value.toLowerCase()}`}>
                                    {option.badge}
                                  </span>
                                  <div>
                                    <strong>{option.label}</strong>
                                    <p className="muted">{option.detail}</p>
                                  </div>
                                </div>
                                <span className="onboarding-format-option__method">
                                  {option.method === 'API' ? 'REST API' : 'File Upload'}
                                </span>
                              </label>
                            );
                          })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Step 3: Schema Mapping Workbench */}
            <div className="onboarding-card">
              <div className="onboarding-card__header">
                <div className="onboarding-card__title-wrap">
                  <div className="onboarding-step-badge">STEP 3 OF 3</div>
                  <h2>Canonical Schema Mapping Workbench</h2>
                  <p className="muted">
                    Map incoming dealer fields to the Daimler OEM canonical standard. Test previews verify compliance.
                  </p>
                </div>
              </div>

              {/* Format Switcher Tabs */}
              <div className="onboarding-tabs-container">
                <div className="onboarding-tabs-bar" role="tablist" aria-label="Format profiles">
                  {selectedFormats.map((format) => {
                    const isTabActive = activeFormat === format;
                    const isPreviewed = format === 'PDF' || previews[format]?.signature === serialize({ mapping: drafts[format].mapping, sample: drafts[format].sample });

                    return (
                      <button
                        type="button"
                        role="tab"
                        aria-selected={isTabActive}
                        className={`onboarding-tab ${isTabActive ? 'onboarding-tab--active' : ''}`}
                        key={format}
                        onClick={() => setActiveFormat(format)}
                      >
                        <span className={`format-tag format-tag--${format.toLowerCase()}`}>{format}</span>
                        <span>{formatLabel(format)}</span>
                        {isPreviewed && (
                          <span className="onboarding-tab__check" title="Preview validated">
                            ✓
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>

                <div className="onboarding-active-summary">
                  <div className="onboarding-active-fact">
                    <span className="muted">Active Tier:</span>
                    <strong>Tier {formatConfig(activeFormat).tier}</strong>
                  </div>
                  <div className="onboarding-active-fact">
                    <span className="muted">Transmission:</span>
                    <strong>{formatConfig(activeFormat).method === 'API' ? 'Direct HTTPS REST API' : 'Multipart File Upload'}</strong>
                  </div>
                  <div className="onboarding-active-fact">
                    <span className="muted">Parser Type:</span>
                    <strong>{activeFormat === 'PDF' ? 'OCR & Table Parser' : 'Deterministic Canonical Normalizer'}</strong>
                  </div>
                </div>
              </div>

              <div className="onboarding-card__content">
                {structured ? (
                  <>
                    <Notice>
                      {activeFormat === 'JSON' ? (
                        <>
                          <strong>JSON Parser:</strong> Maps exact dotted field paths from your inbound payload to canonical Daimler OEM schema. No AI guesswork is applied.
                        </>
                      ) : (
                        <>
                          <strong>Tabular Parser:</strong> Reads header columns from the initial row, and line item columns from each row under <code className="code">rows</code>.
                        </>
                      )}
                    </Notice>

                    <div className="onboarding-workbench-grid">
                      {/* Left: Source Mapping Editor */}
                      <div className="onboarding-workbench-panel">
                        <div className="onboarding-workbench-panel__header">
                          <div>
                            <h3>Field Path Mapping</h3>
                            <p className="muted">Configure path expressions pointing to the incoming fields.</p>
                          </div>
                        </div>

                        <div className="onboarding-mapping-section">
                          <h4 className="onboarding-subheading">INVOICE HEADER ATTRIBUTES</h4>
                          <div className="onboarding-mapping-list">{mappingRows(false)}</div>
                        </div>

                        <div className="onboarding-mapping-section">
                          <h4 className="onboarding-subheading">INVOICE LINE ITEM ATTRIBUTES</h4>
                          <p className="muted" style={{ marginBottom: '10px' }}>
                            <code className="code">source_field</code> specifies the root array path. Line fields are resolved relative to each line object.
                          </p>
                          <div className="onboarding-mapping-list">{mappingRows(true)}</div>
                        </div>
                      </div>

                      {/* Right: Sample Editor & Live Preview */}
                      <div className="onboarding-workbench-panel">
                        <div className="onboarding-workbench-panel__header">
                          <div>
                            <h3>Sample Inbound Payload</h3>
                            <p className="muted">Provide representative sample data to test against the mapping.</p>
                          </div>
                          <div className="onboarding-workbench-actions">
                            <button
                              type="button"
                              className="button button--secondary button--sm"
                              onClick={() => {
                                updateDraft(activeFormat, {
                                  mapping: emptyMapping(),
                                  sample: serialize(activeFormat === 'JSON' ? jsonDemoSource : csvDemoSource),
                                });
                                setPreviews((current) => {
                                  const next = { ...current };
                                  delete next[activeFormat];
                                  return next;
                                });
                              }}
                            >
                              Reset
                            </button>
                            <button
                              type="button"
                              className="button button--primary button--sm"
                              disabled={busy || USE_DEV_MOCK_API}
                              onClick={() => void runPreview()}
                            >
                              {preview.isPending ? 'Verifying…' : 'Test Preview'}
                            </button>
                          </div>
                        </div>

                        <div className="onboarding-code-editor-wrap">
                          <textarea
                            rows={16}
                            value={draft.sample}
                            onChange={(event) => updateDraft(activeFormat, { sample: event.target.value })}
                            spellCheck={false}
                            className="onboarding-code-textarea"
                            aria-label="Sample payload JSON"
                          />
                        </div>

                        {/* Preview Results Banner */}
                        <div className="onboarding-preview-result">
                          {activePreview && activePreview.signature === signature ? (
                            <div className="onboarding-preview-success">
                              <div className="onboarding-preview-success__header">
                                <span className="badge badge--success">✓ Schema Preview Passed</span>
                                <small className="muted">Canonical record verified against Daimler OEM spec</small>
                              </div>
                              <pre className="onboarding-canonical-preview" tabIndex={0} aria-label="Server canonical mapping preview">
                                {serialize(activePreview.candidate)}
                              </pre>
                            </div>
                          ) : (
                            <div className="onboarding-preview-pending">
                              <span className="onboarding-preview-pending__icon">ℹ</span>
                              <div>
                                <strong>Preview Required for Registration</strong>
                                <p className="muted">Click &ldquo;Test Preview&rdquo; above to run test extraction against the server normalizer.</p>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  /* PDF Special Profile Notice */
                  <div className="onboarding-pdf-info">
                    <div className="onboarding-pdf-info__icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                    </div>
                    <div>
                      <h3>Digital PDF Auto-Normalizer</h3>
                      <p className="muted">
                        PDF profiles operate through the OneDMS OCR, layout analysis, and local parser engine. Schema field mapping is handled dynamically by the extraction pipeline.
                      </p>
                      <div className="onboarding-pdf-features">
                        <span>• OCR text extraction</span>
                        <span>• Multi-page table reconstruction</span>
                        <span>• Automated VIN & Part code detection</span>
                        <span>• Human review queue routing</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Registration Action Bar */}
            <div className="onboarding-submit-bar">
              <div className="onboarding-submit-bar__info">
                <strong>
                  {selectedFormats.length} DMS Profile{selectedFormats.length === 1 ? '' : 's'} Ready
                </strong>
                <div className="onboarding-submit-bar__tags">
                  {selectedFormats.map((fmt) => (
                    <span key={fmt} className={`format-tag format-tag--${fmt.toLowerCase()}`}>
                      {fmt}
                    </span>
                  ))}
                </div>
              </div>

              <div className="onboarding-submit-bar__actions">
                <button
                  type="submit"
                  className="button button--primary"
                  disabled={busy || USE_DEV_MOCK_API || !name.trim() || !allMappingsPreviewed}
                >
                  {create.isPending ? 'Registering Profiles…' : 'Register DMS Profiles'}
                </button>
              </div>
            </div>
          </fieldset>

          {(localError || create.isError) && (
            <Notice kind="error">{localError || create.error?.message}</Notice>
          )}
        </form>
      )}
    </section>
  );
}