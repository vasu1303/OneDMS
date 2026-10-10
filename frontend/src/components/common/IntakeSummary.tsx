export default function IntakeSummary({ dealer, dms, format, mapping }: { dealer: string; dms: string; format: string; mapping: string }) {
  return <dl className="ledger-strip intake-summary" aria-label="Source integration summary">
    <div><dt>Dealer</dt><dd>{dealer}</dd></div>
    <div><dt>DMS profile</dt><dd>{dms}</dd></div>
    <div><dt>Source format</dt><dd>{format}</dd></div>
    <div><dt>Mapping / review</dt><dd>{mapping}</dd></div>
  </dl>;
}