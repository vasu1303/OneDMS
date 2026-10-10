import { useMutation } from '@tanstack/react-query';
import { getApprovedInvoicePdf, USE_DEV_MOCK_API } from '@/services/api';
import Notice from '@/components/common/Notice';
import type { Id } from '@/types';

export default function ApprovedInvoiceDownload({ invoiceId, invoiceNumber, approved }: { invoiceId: Id; invoiceNumber?: string; approved: boolean }) {
  const download = useMutation({
    mutationFn: async () => {
      const blob = await getApprovedInvoicePdf(invoiceId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const safeName = (invoiceNumber || `invoice-${invoiceId}`).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 80);
      link.href = url;
      link.download = `approved-${safeName}.pdf`;
      try {
        document.body.appendChild(link);
        link.click();
      } finally {
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
      }
    },
  });
  return <div className="stack download-panel">
    <div className="actions"><button type="button" className="button button--primary" disabled={!approved || download.isPending || USE_DEV_MOCK_API} onClick={() => download.mutate()}>{download.isPending ? 'Preparing approved PDF…' : 'Download approved invoice PDF'}</button></div>
    <p className="muted">{USE_DEV_MOCK_API ? 'Final PDF download is unsupported in development fixture mode; no mock document is substituted.' : approved ? 'Final PDF from the saved, approved canonical invoice. This is not the original source file.' : 'A final invoice PDF is available only after approval.'}</p>
    {download.isError && <Notice kind="error">PDF download failed: {download.error.message}</Notice>}
    {download.isSuccess && <p className="save-feedback" role="status">Approved PDF download requested.</p>}
  </div>;
}