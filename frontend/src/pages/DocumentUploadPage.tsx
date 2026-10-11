import { useState } from 'react';
import type { DragEvent, FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useUploadDocument } from '@/hooks/useInvoiceWorkflow';
import { useDealers, useDmsSystems } from '@/hooks/useRegistry';
import { USE_DEV_MOCK_API } from '@/services/api';
import IntakeSummary from '@/components/common/IntakeSummary';
import Notice from '@/components/common/Notice';
import type { SourceType } from '@/types';

const sourceTypes: Array<{ type: SourceType; label: string; badge: string; desc: string }> = [
  { type: 'pdf', label: 'Digital PDF', badge: 'PDF', desc: 'OCR & Layout Parser' },
  { type: 'excel', label: 'Excel Sheet', badge: 'XLSX / XLS', desc: 'Worksheet Header & Lines' },
  { type: 'csv', label: 'CSV Flatfile', badge: 'CSV EDI', desc: 'Delimited Catalog Rows' },
  { type: 'json', label: 'JSON API Feed', badge: 'JSON', desc: 'Structured Payload Feed' },
];

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function DocumentUploadPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const dealers = useDealers();
  const systems = useDmsSystems();
  const [dealerId, setDealerId] = useState('');
  const [dmsSystemId, setDmsSystemId] = useState(searchParams.get('dms_id') ?? '');
  const [selectedSourceType, setSelectedSourceType] = useState<SourceType>('pdf');
  const [file, setFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [localError, setLocalError] = useState('');

  const selectedDealer = dealers.data?.find((dealer) => String(dealer.id) === dealerId);
  const selectedDms = systems.data?.find((system) => String(system.id) === dmsSystemId);
  const sourceType = selectedSourceType;

  const uploadMutation = useUploadDocument((progress) => setUploadProgress(progress));

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setLocalError('');
    }
  };

  const submitFile = async () => {
    if (!file) {
      throw new Error('Please select or drop an invoice file to proceed.');
    }

    const response = await uploadMutation.mutateAsync({
      dealer_id: dealerId.trim(),
      dms_id: dmsSystemId.trim(),
      source_type: sourceType,
      file,
    });

    return response.id;
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (uploadMutation.isPending) return;
    setLocalError('');
    setUploadProgress(0);
    uploadMutation.reset();

    if (!dealerId.trim() || !dmsSystemId.trim()) {
      setLocalError('Select both a registered dealer and a DMS integration profile.');
      return;
    }
    if (!USE_DEV_MOCK_API && (!selectedDealer || !selectedDms)) {
      setLocalError('Choose a valid registered dealer and a DMS integration profile.');
      return;
    }
    if (!file) {
      setLocalError('Please attach an invoice file to upload.');
      return;
    }

    try {
      const documentId = await submitFile();
      navigate(`/documents/${documentId}`);
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : 'Submission failed. Please check network connectivity.');
    } finally {
      setUploadProgress(0);
    }
  };

  const isSubmitting = uploadMutation.isPending;

  return (
    <section className="view intake-view">
      <header className="view__header">
        <div>
          <div className="view__eyebrow">
            <span>CENTRAL INGESTION PIPELINE</span>
          </div>
          <h1>Invoice Intake & Normalization</h1>
          <p className="muted">
            Submit dealer invoices to extract, standardize, and validate into canonical OEM format.
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

      {/* Intake Context Strip */}
      <IntakeSummary
        dealer={selectedDealer ? `${selectedDealer.name} (${selectedDealer.dealer_code})` : USE_DEV_MOCK_API ? dealerId || 'Fixture Dealer' : 'Select dealer profile'}
        dms={selectedDms ? `${selectedDms.name} · ${selectedDms.input_format}` : USE_DEV_MOCK_API ? dmsSystemId || 'Fixture DMS' : 'Select source DMS'}
        format={selectedDms || USE_DEV_MOCK_API ? sourceType.toUpperCase() : 'Not selected'}
        mapping={selectedDms?.active_mapping_version != null ? `Canonical v${selectedDms.active_mapping_version}` : selectedDms?.input_format === 'PDF' ? 'PDF Text & LLM Normalizer' : 'Profile mapping ready'}
      />

      {!USE_DEV_MOCK_API && (dealers.isError || systems.isError) && (
        <Notice kind="error">
          <p>Registry service unavailable: {dealers.error?.message || systems.error?.message}</p>
          <button type="button" className="button button--secondary" onClick={() => { void dealers.refetch(); void systems.refetch(); }}>
            Retry Registries
          </button>
        </Notice>
      )}

      <form className="form intake-form-modern" onSubmit={onSubmit}>
        <fieldset disabled={isSubmitting}>
          {/* Step 1: Integration Profiling */}
          <div className="form-card">
            <div className="form-card__header">
              <span className="step-badge">STEP 1</span>
              <div>
                <strong>Ingestion Routing & System Binding</strong>
                <p className="muted">Identify the originating dealer and DMS configuration profile.</p>
              </div>
            </div>

            <div className="form-grid">
              <label>
                <span>Registered Dealership</span>
                {USE_DEV_MOCK_API ? (
                  <input
                    required
                    type="text"
                    value={dealerId}
                    onChange={(e) => setDealerId(e.target.value)}
                    placeholder="Enter fixture dealer ID"
                  />
                ) : (
                  <select
                    required
                    value={dealerId}
                    disabled={!dealers.data?.length}
                    onChange={(e) => setDealerId(e.target.value)}
                  >
                    <option value="">Select a registered dealership...</option>
                    {dealers.data?.map((dealer) => (
                      <option key={dealer.id} value={String(dealer.id)}>
                        {dealer.name} ({dealer.dealer_code})
                      </option>
                    ))}
                  </select>
                )}
              </label>

              <label>
                <span>Source DMS System Profile</span>
                {USE_DEV_MOCK_API ? (
                  <input
                    required
                    type="text"
                    value={dmsSystemId}
                    onChange={(e) => { setDmsSystemId(e.target.value); setFile(null); setLocalError(''); }}
                    placeholder="Enter fixture DMS ID"
                  />
                ) : (
                  <select
                    required
                    value={dmsSystemId}
                    disabled={!systems.data?.length}
                    onChange={(e) => { setDmsSystemId(e.target.value); setFile(null); setLocalError(''); }}
                  >
                    <option value="">Select source DMS profile...</option>
                    {systems.data?.map((system) => (
                      <option key={system.id} value={String(system.id)}>
                        {system.name} — Tier {system.integration_tier} ({system.input_format})
                      </option>
                    ))}
                  </select>
                )}
              </label>
            </div>
          </div>

          {/* Step 2: Payload Source Selection & Upload */}
          <div className="form-card">
            <div className="form-card__header">
              <span className="step-badge">STEP 2</span>
              <div>
                <strong>Document Format & File Payload</strong>
                <p className="muted">Select payload type and attach the invoice document.</p>
              </div>
            </div>

            <div className="format-selector-grid">
              {sourceTypes.map((fmt) => (
                <button
                  type="button"
                  key={fmt.type}
                  className={`format-card-btn ${sourceType === fmt.type ? 'format-card-btn--active' : ''}`}
                  onClick={() => { setSelectedSourceType(fmt.type); setFile(null); setLocalError(''); }}
                >
                  <div className="format-card-btn__top">
                    <strong>{fmt.label}</strong>
                    <span className="format-card-btn__badge">{fmt.badge}</span>
                  </div>
                  <small>{fmt.desc}</small>
                </button>
              ))}
            </div>

            {/* Drag & Drop File Zone */}
            <div
              className={`dropzone ${isDragOver ? 'dropzone--active' : ''} ${file ? 'dropzone--has-file' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                id="file-upload-input"
                type="file"
                className="dropzone__input"
                key={sourceType}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />

              {!file ? (
                <label htmlFor="file-upload-input" className="dropzone__content">
                  <div className="dropzone__icon-circle">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <div className="dropzone__text">
                    <strong>Choose a file or drag & drop it here</strong>
                    <p className="muted">
                      Supported formats: PDF, CSV, Excel (.xlsx, .xls), JSON (Max 10 MB)
                    </p>
                  </div>
                  <span className="button button--secondary button--sm">Browse Files</span>
                </label>
              ) : (
                <div className="selected-file-preview">
                  <div className="file-info-col">
                    <div className="file-icon-badge">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                        <line x1="16" y1="13" x2="8" y2="13" />
                        <line x1="16" y1="17" x2="8" y2="17" />
                        <polyline points="10 9 9 9 8 9" />
                      </svg>
                    </div>
                    <div>
                      <strong className="file-name">{file.name}</strong>
                      <div className="file-meta">
                        <span>{formatBytes(file.size)}</span>
                        <span>•</span>
                        <span className="file-type-pill">{sourceType.toUpperCase()}</span>
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => setFile(null)}
                  >
                    Change File
                  </button>
                </div>
              )}
            </div>

            <div className="format-instruction">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              <span>
                {sourceType === 'pdf'
                  ? 'Digital PDF text extraction will identify invoice headers, totals, line items, and chassis/VIN numbers.'
                  : sourceType === 'excel'
                  ? 'Excel workbooks (.xlsx, .xls) will map sheet headers to canonical Daimler fields automatically.'
                  : sourceType === 'csv'
                  ? 'CSV files will parse header rows and line items against the selected DMS profile catalog mapping.'
                  : 'JSON feeds will be parsed against registered DMS schema bindings.'}
              </span>
            </div>
          </div>

          {/* Action Row */}
          <div className="intake-actions">
            <button
              type="submit"
              className="button button--primary button--lg"
              disabled={isSubmitting || (!USE_DEV_MOCK_API && (!selectedDealer || !selectedDms || !file))}
            >
              {isSubmitting ? (
                <>
                  <span className="button-spinner"></span>
                  <span>Ingesting & Processing...</span>
                </>
              ) : (
                <>
                  <span>Submit Document for Processing</span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </fieldset>

        {isSubmitting && (
          <div className="upload-progress-card" role="status">
            <div className="progress-label-row">
              <span className="muted">
                {uploadProgress === 100
                  ? 'File uploaded. Running extraction & validation engine...'
                  : `Transmitting payload to object storage (${uploadProgress}%)...`}
              </span>
              <strong>{uploadProgress}%</strong>
            </div>
            <div className="progress-track">
              <div
                className="progress-bar-fill"
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
          </div>
        )}

        {localError && (
          <div className="panel panel--error" role="alert">
            <div className="error-title-row">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <strong>Submission Error</strong>
            </div>
            <p>{localError}</p>
          </div>
        )}
      </form>
    </section>
  );
}

export default DocumentUploadPage;
