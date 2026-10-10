import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useUploadDocument, useUploadJsonDocument } from '@/hooks/useInvoiceWorkflow';
import { useDealers, useDmsSystems } from '@/hooks/useRegistry';
import { USE_DEV_MOCK_API } from '@/services/api';
import IntakeSummary from '@/components/common/IntakeSummary';
import Notice from '@/components/common/Notice';
import { jsonDemoSource } from '@/constants/integrationDemo';
import type { SourceType } from '@/types';

const sourceTypes: SourceType[] = ['pdf', 'csv', 'json'];

type InputMode = 'file' | 'json';

function DocumentUploadPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const dealers = useDealers();
  const systems = useDmsSystems();
  const [mode, setMode] = useState<InputMode>('file');
  const [dealerId, setDealerId] = useState('');
  const [dmsSystemId, setDmsSystemId] = useState(searchParams.get('dms_id') ?? '');
  const [sourceType, setSourceType] = useState<SourceType>('pdf');
  const selectedDealer = dealers.data?.find((dealer) => String(dealer.id) === dealerId);
  const selectedDms = systems.data?.find((system) => String(system.id) === dmsSystemId);
  const activeMode = sourceType === 'json' ? mode : 'file';
  const [file, setFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState(JSON.stringify(jsonDemoSource, null, 2));
  const [uploadProgress, setUploadProgress] = useState(0);
  const [localError, setLocalError] = useState('');

  const uploadMutation = useUploadDocument((progress) => setUploadProgress(progress));
  const uploadJsonMutation = useUploadJsonDocument();

  const submitFile = async () => {
    if (!file) {
      throw new Error('Choose a file before upload.');
    }
    if (!file.name.toLowerCase().endsWith(`.${sourceType}`)) {
      throw new Error(`Choose a .${sourceType} file or change the source type to match your file.`);
    }

    const response = await uploadMutation.mutateAsync({
      dealer_id: dealerId.trim(),
      dms_id: dmsSystemId.trim(),
      source_type: sourceType,
      file,
    });

    return response.id;
  };

  const submitJson = async () => {
    let payload: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(jsonText);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('JSON must be an object, not an array, scalar, or null.');
      payload = parsed as Record<string, unknown>;
    } catch (error) {
      throw new Error(error instanceof SyntaxError ? 'JSON is malformed. Correct the syntax and submit again.' : error instanceof Error ? error.message : 'JSON payload is not valid.');
    }

    const response = await uploadJsonMutation.mutateAsync({
      dealer_id: dealerId.trim(),
      dms_id: dmsSystemId.trim(),
      payload,
    });

    return response.id;
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (uploadMutation.isPending || uploadJsonMutation.isPending) return;
    setLocalError(''); setUploadProgress(0); uploadMutation.reset(); uploadJsonMutation.reset();

    if (!dealerId.trim() || !dmsSystemId.trim()) {
      setLocalError('Select a dealer and DMS integration profile.');
      return;
    }
    if (!USE_DEV_MOCK_API && (!selectedDealer || !selectedDms || !sourceTypes.includes(sourceType))) {
      setLocalError('Choose a registered dealer, a source DMS, and a PDF, CSV, or JSON source type.');
      return;
    }

    try {
      const documentId = activeMode === 'file' ? await submitFile() : await submitJson();
      navigate(`/documents/${documentId}`);
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : 'Submission failed. Retry.');
    } finally {
      setUploadProgress(0);
    }
  };

  const isSubmitting = uploadMutation.isPending || uploadJsonMutation.isPending;
  const error = localError;

  return (
    <section className="view">
      <header className="view__header">
        <div>
          <h1>Invoice intake</h1>
          <p className="muted">Select a dealer and source system, then upload an invoice for review.</p>
        </div>
        <Link to="/documents" className="button button--secondary">
          Back to queue
        </Link>
      </header>

      <IntakeSummary dealer={selectedDealer ? `${selectedDealer.name} · ${selectedDealer.dealer_code}` : USE_DEV_MOCK_API ? dealerId || 'Fixture dealer' : 'Select dealer'} dms={selectedDms ? `${selectedDms.name} · #${selectedDms.id}` : USE_DEV_MOCK_API ? dmsSystemId || 'Fixture DMS' : 'Select profile'} format={selectedDms || USE_DEV_MOCK_API ? sourceType.toUpperCase() : 'Not selected'} mapping={selectedDms?.active_mapping_version != null ? `Explicit mapping v${selectedDms.active_mapping_version}` : selectedDms?.input_format === 'PDF' ? 'Existing PDF layout parser' : 'Not supplied'} />
      {!USE_DEV_MOCK_API && (dealers.isError || systems.isError) && <Notice kind="error"><p>Registry unavailable: {dealers.error?.message || systems.error?.message}</p><button type="button" className="button button--secondary" onClick={() => { void dealers.refetch(); void systems.refetch(); }}>Retry registries</button></Notice>}
      {!USE_DEV_MOCK_API && (dealers.isLoading || systems.isLoading) && <p role="status">Loading dealer and DMS registries…</p>}
      {!USE_DEV_MOCK_API && dealers.isSuccess && dealers.data.length === 0 && <Notice>No dealers are registered. Ask the API owner to add a dealer before intake.</Notice>}
      {!USE_DEV_MOCK_API && systems.isSuccess && systems.data.length === 0 && <Notice>No source systems are available. Ask the API owner to configure the demo systems.</Notice>}
      {!USE_DEV_MOCK_API && dmsSystemId && systems.isSuccess && !selectedDms && <Notice kind="error">DMS #{dmsSystemId} is not in the current registry. Select an available profile.</Notice>}
      <form className="form intake-form" onSubmit={onSubmit}>
        <fieldset disabled={isSubmitting}><legend className="sr-only">Document submission</legend>
        {USE_DEV_MOCK_API && <Notice>Development-only fixture intake. These submissions do not create live records.</Notice>}
        <div className="form-grid">
          <label>
            {USE_DEV_MOCK_API ? 'Fixture dealer ID' : 'Registered dealer'}
            {USE_DEV_MOCK_API ? <input
              required
              type="text"
              value={dealerId}
              onChange={(event) => setDealerId(event.target.value)}
              placeholder="Development fixture identifier"
            /> : <select required value={dealerId} disabled={!dealers.data?.length} onChange={(event) => setDealerId(event.target.value)}><option value="">Select dealer</option>{dealers.data?.map((dealer) => <option key={dealer.id} value={String(dealer.id)}>{dealer.name} · {dealer.dealer_code} · #{dealer.id}</option>)}</select>}
          </label>

          <label>
            {USE_DEV_MOCK_API ? 'Fixture DMS ID' : 'Source DMS'}
            {USE_DEV_MOCK_API ? <input
              required
              type="text"
              value={dmsSystemId}
              onChange={(event) => setDmsSystemId(event.target.value)}
              placeholder="Development fixture identifier"
            /> : <select required value={dmsSystemId} disabled={!systems.data?.length} onChange={(event) => { setDmsSystemId(event.target.value); setLocalError(''); }}><option value="">Select source DMS</option>{systems.data?.map((system) => <option key={system.id} value={String(system.id)}>{system.name} · #{system.id}</option>)}</select>}
          </label>

          <label>
            Source type
            <select
              value={sourceType}
              onChange={(event) => { setSourceType(event.target.value as SourceType); setFile(null); setLocalError(''); }}
            >
              {sourceTypes.map((type) => (
                <option key={type} value={type}>
                  {type.toUpperCase()}
                </option>
              ))}
            </select>
          </label>

          <label>
            Submission mode
            <select
              value={activeMode}
              onChange={(event) => { setMode(event.target.value as InputMode); setLocalError(''); setUploadProgress(0); }}
            >
              <option value="file">Multipart file</option>
              {sourceType === 'json' && <option value="json">JSON payload</option>}
            </select>
          </label>
        </div>

        {activeMode === 'file' ? (
          <label>
            Invoice file
            <input
              required
              type="file"
              key={sourceType}
              accept={`.${sourceType}`}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
        ) : (
          <label>
            JSON payload
            <textarea
              aria-label="JSON payload"
              rows={14}
              value={jsonText}
              onChange={(event) => setJsonText(event.target.value)}
              spellCheck={false}
            />
          </label>
        )}

        <Notice>{sourceType === 'pdf' ? 'Any registered source DMS can submit a PDF. Select the DMS that produced it, then choose your file. Extraction and amount checks happen after upload; scanned or unfamiliar layouts may fail processing or need review.' : sourceType === 'csv' ? 'Use the supported demo CSV column layout and a matching source mapping.' : 'JSON field names must match the selected source system’s configured mapping.'}</Notice>

        <div className="actions"><button type="submit" className="button button--primary" disabled={isSubmitting || (!USE_DEV_MOCK_API && (!selectedDealer || !selectedDms || !sourceTypes.includes(sourceType)))}>{isSubmitting ? 'Submitting…' : 'Submit document'}</button></div>
        </fieldset>

        {isSubmitting && activeMode === 'file' ? (
          <div role="status"><p className="muted">{uploadProgress === 100 ? 'File sent. Waiting for the server to accept the document…' : `Uploading file… ${uploadProgress}%`}</p><progress aria-label="File upload progress" max={100} value={uploadProgress} /></div>
        ) : null}

        {isSubmitting && activeMode === 'json' ? <p className="muted" role="status">Submitting JSON. Waiting for the server response…</p> : null}

        {error ? (
          <p className="panel panel--error" role="alert">
            Submission failed: {error}
          </p>
        ) : null}

      </form>
    </section>
  );
}

export default DocumentUploadPage;
