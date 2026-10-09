import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useUploadDocument, useUploadJsonDocument } from '@/hooks/useInvoiceWorkflow';
import type { SourceType } from '@/types';

const sourceTypes: SourceType[] = ['pdf', 'json', 'xml', 'csv', 'excel', 'flatfile'];

type InputMode = 'file' | 'json';

function DocumentUploadPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<InputMode>('file');
  const [dealerId, setDealerId] = useState('');
  const [dmsSystemId, setDmsSystemId] = useState('');
  const [sourceType, setSourceType] = useState<SourceType>('pdf');
  const [file, setFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState('{\n  "invoice_number": ""\n}');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [localError, setLocalError] = useState('');

  const uploadMutation = useUploadDocument((progress) => setUploadProgress(progress));
  const uploadJsonMutation = useUploadJsonDocument();

  const submitFile = async () => {
    if (!file) {
      throw new Error('Choose a file before upload.');
    }

    const response = await uploadMutation.mutateAsync({
      dealer_id: dealerId.trim(),
      dms_system_id: dmsSystemId.trim(),
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
      dms_system_id: dmsSystemId.trim(),
      payload,
    });

    return response.id;
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (uploadMutation.isPending || uploadJsonMutation.isPending) return;
    setLocalError(''); setUploadProgress(0); uploadMutation.reset(); uploadJsonMutation.reset();

    if (!dealerId.trim() || !dmsSystemId.trim()) {
      setLocalError('Enter the dealer and DMS system identifiers.');
      return;
    }

    try {
      const documentId = mode === 'file' ? await submitFile() : await submitJson();
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
          <p className="muted">Submit a dealer document for invoice processing.</p>
        </div>
        <Link to="/documents" className="button button--secondary">
          Back to queue
        </Link>
      </header>

      <form className="form" onSubmit={onSubmit}>
        <fieldset disabled={isSubmitting}><legend className="sr-only">Document submission</legend>
        <p className="notice">Enter identifiers provided by your workflow API owner. Dealer and DMS registry options are not connected in this POC.</p>
        <div className="form-grid">
          <label>
            Dealer ID
            <input
              required
              type="text"
              value={dealerId}
              onChange={(event) => setDealerId(event.target.value)}
              placeholder="Assigned dealer identifier"
            />
          </label>

          <label>
            DMS system ID
            <input
              required
              type="text"
              value={dmsSystemId}
              onChange={(event) => setDmsSystemId(event.target.value)}
              placeholder="Assigned DMS identifier"
            />
          </label>

          <label>
            Source type
            <select
              value={mode === 'json' ? 'json' : sourceType}
              disabled={mode === 'json'}
              onChange={(event) => setSourceType(event.target.value as SourceType)}
            >
              {sourceTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>

          <label>
            Submission mode
            <select
              value={mode}
              onChange={(event) => { setMode(event.target.value as InputMode); setLocalError(''); setUploadProgress(0); }}
            >
              <option value="file">Multipart file</option>
              <option value="json">JSON payload</option>
            </select>
          </label>
        </div>

        {mode === 'file' ? (
          <label>
            Invoice file
            <input
              required
              type="file"
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

        <p className="muted">File formats represented by the provisional contract: PDF, JSON, XML, CSV, Excel, and flat file. Choose the matching source type; server support must be confirmed.</p>

        <div className="actions"><button type="submit" className="button button--primary" disabled={isSubmitting}>{isSubmitting ? 'Submitting…' : 'Submit document'}</button></div>
        </fieldset>

        {isSubmitting && mode === 'file' ? (
          <div role="status"><p className="muted">{uploadProgress === 100 ? 'File sent. Waiting for the server to accept the document…' : `Uploading file… ${uploadProgress}%`}</p><progress aria-label="File upload progress" max={100} value={uploadProgress} /></div>
        ) : null}

        {isSubmitting && mode === 'json' ? <p className="muted" role="status">Submitting JSON. Waiting for the server response…</p> : null}

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
