import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  getDocument,
  getDocuments,
  getInvoice,
  patchInvoice,
  processDocument,
  reviewInvoice,
  uploadDocument,
  uploadDocumentJson,
} from '@/services/api';
import type {
  DocumentDetail,
  DocumentQueueItem,
  DocumentUploadPayload,
  Id,
  InvoiceDetail,
  InvoicePatchPayload,
  InvoiceReviewPayload,
  QueueFilters,
} from '@/types';

export const queryKeys = {
  documents: (filters: QueueFilters) => ['documents', filters] as const,
  document: (documentId: Id) => ['document', documentId] as const,
  invoice: (invoiceId: Id) => ['invoice', invoiceId] as const,
};

export const useDocumentQueue = (
  filters: QueueFilters,
): UseQueryResult<DocumentQueueItem[], Error> =>
  useQuery({
    queryKey: queryKeys.documents(filters),
    queryFn: () => getDocuments(filters),
    refetchInterval: (query) => {
      const items = query.state.data;
      if (!items?.length) {
        return false;
      }

      const hasProcessing = items.some(
        (item) =>
          item.processing_status === 'processing' ||
          item.processing_status === 'received',
      );
      return hasProcessing ? 5000 : false;
    },
  });

export const useDocumentDetail = (
  documentId: Id,
): UseQueryResult<DocumentDetail, Error> =>
  useQuery({
    queryKey: queryKeys.document(documentId),
    queryFn: () => getDocument(documentId),
    enabled: Number.isSafeInteger(documentId) && documentId > 0,
    refetchInterval: (query) => {
      const status = query.state.data?.processing_status;
      return status === 'received' || status === 'processing' ? 5000 : false;
    },
  });

export const useInvoiceDetail = (invoiceId: Id): UseQueryResult<InvoiceDetail, Error> =>
  useQuery({
    queryKey: queryKeys.invoice(invoiceId),
    queryFn: () => getInvoice(invoiceId),
    enabled: Number.isSafeInteger(invoiceId) && invoiceId > 0,
  });

export const useUploadDocument = (onProgress: (progress: number) => void) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DocumentUploadPayload) => uploadDocument(payload, onProgress),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
};

export const useUploadJsonDocument = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadDocumentJson,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
};

export const useProcessDocument = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: processDocument,
    onSuccess: (document) => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
      void queryClient.setQueryData(queryKeys.document(document.id), document);
      void queryClient.invalidateQueries({ queryKey: queryKeys.document(document.id) });
      if (document.invoice_id) void queryClient.invalidateQueries({ queryKey: queryKeys.invoice(document.invoice_id) });
    },
  });
};

export const usePatchInvoice = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ invoiceId, payload }: { invoiceId: Id; payload: InvoicePatchPayload }) =>
      patchInvoice(invoiceId, payload),
    onSuccess: (invoice) => {
      void queryClient.setQueryData(queryKeys.invoice(invoice.id), invoice);
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.document(invoice.document_id) });
    },
  });
};

export const useReviewInvoice = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ invoiceId, payload }: { invoiceId: Id; payload: InvoiceReviewPayload }) =>
      reviewInvoice(invoiceId, payload),
    onSuccess: (invoice) => {
      void queryClient.setQueryData(queryKeys.invoice(invoice.id), invoice);
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.document(invoice.document_id) });
    },
  });
};
