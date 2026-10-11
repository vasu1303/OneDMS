interface IntakeSummaryProps {
  dealer: string;
  dms: string;
  format: string;
  mapping: string;
}

export default function IntakeSummary({ dealer, dms, format, mapping }: IntakeSummaryProps) {
  const isDealerPlaceholder = dealer.toLowerCase().includes('select') || dealer.toLowerCase().includes('not');
  const isDmsPlaceholder = dms.toLowerCase().includes('select') || dms.toLowerCase().includes('not');
  const isFormatPlaceholder = format.toLowerCase().includes('select') || format.toLowerCase().includes('not');

  return (
    <div className="intake-summary-bar" role="region" aria-label="Ingestion route context">
      <div className="intake-summary-item">
        <div className="intake-summary-icon intake-summary-icon--blue">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 21h18M3 7v14M21 7v14M6 11h4M6 15h4M14 11h4M14 15h4M9 3l3-2 3 2v4H9V3z" />
          </svg>
        </div>
        <div className="intake-summary-text">
          <span className="intake-summary-label">ORIGINATING DEALER</span>
          <strong className={`intake-summary-val ${isDealerPlaceholder ? 'intake-summary-val--placeholder' : ''}`}>
            {dealer}
          </strong>
        </div>
      </div>

      <div className="intake-summary-item">
        <div className="intake-summary-icon intake-summary-icon--purple">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
            <line x1="6" y1="6" x2="6.01" y2="6" />
            <line x1="6" y1="18" x2="6.01" y2="18" />
          </svg>
        </div>
        <div className="intake-summary-text">
          <span className="intake-summary-label">DMS SYSTEM PROFILE</span>
          <strong className={`intake-summary-val ${isDmsPlaceholder ? 'intake-summary-val--placeholder' : ''}`}>
            {dms}
          </strong>
        </div>
      </div>

      <div className="intake-summary-item">
        <div className="intake-summary-icon intake-summary-icon--amber">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </div>
        <div className="intake-summary-text">
          <span className="intake-summary-label">SOURCE FORMAT</span>
          <div className="intake-summary-val-wrap">
            {!isFormatPlaceholder ? (
              <span className={`format-tag format-tag--${format.toLowerCase()}`}>{format}</span>
            ) : (
              <strong className="intake-summary-val intake-summary-val--placeholder">{format}</strong>
            )}
          </div>
        </div>
      </div>

      <div className="intake-summary-item">
        <div className="intake-summary-icon intake-summary-icon--green">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>
        <div className="intake-summary-text">
          <span className="intake-summary-label">ROUTING / MAPPING STATE</span>
          <strong className="intake-summary-val intake-summary-val--success">
            {mapping}
          </strong>
        </div>
      </div>
    </div>
  );
}