import { useEffect, useState } from 'react';
import { getDocumentSource, USE_DEV_MOCK_API } from '@/services/api';
import type { Id } from '@/types';

type SourceState = { url: string; type: string; text?: string } | { error: string } | null;

export default function SourcePreview({ documentId }: { documentId: Id }) {
  const [attempt, setAttempt] = useState(0);
  return <SourceAttempt key={`${documentId}-${attempt}`} documentId={documentId} retry={() => setAttempt((value) => value + 1)} />;
}

function SourceAttempt({ documentId, retry }: { documentId: Id; retry: () => void }) {
  const [source, setSource] = useState<SourceState>(null);
  useEffect(() => {
    const controller = new AbortController();
    let url: string | undefined;
    void getDocumentSource(documentId, controller.signal).then(async (blob) => {
      const type = blob.type.split(';')[0];
      const isText = type.startsWith('text/') || ['application/json', 'application/xml'].includes(type);
      const text = isText ? await blob.text() : undefined;
      if (controller.signal.aborted) return;
      url = URL.createObjectURL(blob);
      setSource({ url, type, text });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setSource({ error: error instanceof Error ? error.message : 'Could not load original source.' });
    });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [documentId]);

  return <article className="source-panel stack" aria-labelledby="source-heading">
    <header><h2 id="source-heading">Original document</h2><p className="muted">Retained source for document #{documentId}</p></header>
    {USE_DEV_MOCK_API && <p className="notice">Development fixture mode. Only your actual submitted file or JSON is previewed; seeded originals are not available.</p>}
    {!source && <p role="status">Loading original from the source endpoint…</p>}
    {source && 'error' in source && <div className="panel panel--error" role="alert"><p>{source.error}</p><button className="button button--secondary" onClick={retry}>Retry source</button></div>}
    {source && 'url' in source && <>
      <div className="actions"><a className="button button--secondary" href={source.url} download={`document-${documentId}`}>Download original</a></div>
      {source.text !== undefined ? <pre className="source-text" tabIndex={0} aria-label="Original document text">{source.text}</pre>
        : source.type === 'application/pdf' ? <object className="source-pdf" data={source.url} type="application/pdf" aria-label={`Original PDF for document ${documentId}`}><p>Your browser cannot preview this PDF. Use Download original.</p></object>
        : <p className="notice">Inline preview is not available for this format ({source.type || 'unknown content type'}). Download the original and inspect it in a compatible viewer.</p>}
    </>}
  </article>;
}