import axios from 'axios';
import type { AxiosProgressEvent } from 'axios';
import type {
  CreateDmsPayload,
  CreateDmsBatchPayload,
  DmsBatchRegistryResult,
  DealerRegistryEntry,
  DmsRegistryEntry,
  MappingPreviewPayload,
  MappingPreviewResult,
  DocumentDetail,
  DocumentQueueItem,
  DocumentUploadPayload,
  Id,
  InvoiceDetail,
  InvoiceLineItem,
  InvoicePatchPayload,
  InvoiceReviewPayload,
  ProcessingStatus,
  QueueFilters,
  ReviewStatus,
  SourceType,
  ValidationFinding,
  ValidationStatus,
} from '@/types';
import {
  getMockDocument,
  getMockDocuments,
  getMockInvoice,
  getMockInvoices,
  mockProcessDocument,
  mockReviewInvoice,
  mockUploadDocument,
  mockUploadJson,
  patchMockInvoice,
  getMockSource,
} from '@/services/mockWorkflowApi';

export const USE_DEV_MOCK_API =
  import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_API === 'true';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

api.interceptors.request.use((config) => config, (error) => Promise.reject(error));

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(error);
    let body: unknown = error.response?.data;
    if (body instanceof Blob) {
      try { body = JSON.parse(await body.text()); } catch { body = undefined; }
    }
    const data = body && typeof body === 'object' ? body as Record<string, unknown> : {};
    const detail = data.detail ?? data.message;
    const describe = (entry: unknown): string => {
      if (!entry || typeof entry !== 'object') return '';
      const finding = entry as Record<string, unknown>;
      const text = typeof finding.message === 'string' ? finding.message : typeof finding.msg === 'string' ? finding.msg : '';
      const field = typeof finding.field === 'string' ? finding.field : Array.isArray(finding.loc) ? finding.loc.join('.') : '';
      return text ? `${field ? `${field}: ` : ''}${text}` : '';
    };
    const nested = detail && typeof detail === 'object' && !Array.isArray(detail) ? detail as Record<string, unknown> : {};
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map(describe).filter(Boolean).join('; ')
      : [typeof nested.message === 'string' ? nested.message : '', ...(Array.isArray(nested.errors) ? nested.errors.map(describe) : [])].filter(Boolean).join('; ');
    return Promise.reject(new Error(message || (error.response
      ? `API request failed (${error.response.status}). Retry or contact the workflow API owner.`
      : 'Cannot reach the workflow API. Check the connection and retry.')));
  },
);

const asNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  return undefined;
};

const asId = (value: unknown): Id => {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('API contract error: expected a positive safe integer ID.');
  }
  return value;
};

const requiredNumber = (value: unknown, field: string): number => {
  const number = asNumber(value);
  if (number === undefined) throw new Error(`API contract error: ${field} must be a finite JSON number.`);
  return number;
};

const asText = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

const asStatus = <T extends string>(
  value: unknown,
  allowed: readonly T[],
  _fallback: T,
): T => {
  if (typeof value === 'string' && allowed.includes(value as T)) {
    return value as T;
  }

  throw new Error('API contract error: missing or unsupported status/source type.');
};

const PROCESSING_STATUSES: readonly ProcessingStatus[] = [
  'received',
  'processing',
  'processed',
  'failed',
  'review_required',
];

const VALIDATION_STATUSES: readonly ValidationStatus[] = [
  'pending',
  'valid',
  'invalid',
  'warning',
];

const REVIEW_STATUSES: readonly ReviewStatus[] = [
  'pending',
  'in_review',
  'approved',
  'rejected',
];

const SOURCE_TYPES: readonly SourceType[] = [
  'json',
  'xml',
  'csv',
  'excel',
  'pdf',
  'flatfile',
];

const normalizeFinding = (payload: unknown, index: number): ValidationFinding => {
  const item = (payload ?? {}) as Record<string, unknown>;
  const severity = asStatus(item.severity, ['error', 'warning', 'info'] as const, 'info');

  return {
    id: item.id == null ? undefined : asId(item.id),
    severity,
    field: item.field ? asText(item.field) : null,
    line_number: asNumber(item.line_number) ?? null,
    message: asText(item.message, `Finding ${index + 1}`),
    confidence: asNumber(item.confidence) ?? null,
    extracted_value: (item.extracted_value as string | number | null) ?? null,
    approved_value: (item.approved_value as string | number | null) ?? null,
  };
};

const normalizeLine = (payload: unknown): InvoiceLineItem => {
  const item = (payload ?? {}) as Record<string, unknown>;

  return {
    id: item.id == null ? undefined : asId(item.id),
    line_number: asId(item.line_number),
    part_number: item.part_number ? asText(item.part_number) : null,
    description: item.description ? asText(item.description) : null,
    quantity: requiredNumber(item.quantity, 'quantity'),
    unit_price: requiredNumber(item.unit_price, 'unit_price'),
    discount_amount: requiredNumber(item.discount_amount, 'discount_amount'),
    tax_amount: requiredNumber(item.tax_amount, 'tax_amount'),
    line_total: requiredNumber(item.line_total, 'line_total'),
    vin: item.vin ? asText(item.vin) : null,
  };
};

const normalizeDocument = (payload: unknown): DocumentQueueItem => {
  const item = (payload ?? {}) as Record<string, unknown>;

  return {
    id: asId(item.id),
    dealer_code: asText(item.dealer_code),
    dealer_name: item.dealer_name ? asText(item.dealer_name) : null,
    dms_name: item.dms_name ? asText(item.dms_name) : null,
    source_type: asStatus(item.source_type, SOURCE_TYPES, 'pdf'),
    source_filename: item.source_filename ? asText(item.source_filename) : null,
    received_at: asText(item.received_at),
    processing_status: asStatus(item.processing_status, PROCESSING_STATUSES, 'received'),
    validation_status: asStatus(item.validation_status, VALIDATION_STATUSES, 'pending'),
    review_status: asStatus(item.review_status, REVIEW_STATUSES, 'pending'),
    summary: item.summary ? asText(item.summary) : null,
    has_findings: Boolean(item.has_findings),
    findings_count: asNumber(item.findings_count),
    invoice_id: item.invoice_id == null ? null : asId(item.invoice_id),
  };
};

const normalizeDocumentDetail = (payload: unknown): DocumentDetail => {
  const item = (payload ?? {}) as Record<string, unknown>;
  const normalized = normalizeDocument(item);

  return {
    ...normalized,
    source_content_type: item.source_content_type
      ? asText(item.source_content_type)
      : null,
    source_size_bytes: asNumber(item.source_size_bytes) ?? null,
    checksum_sha256: item.checksum_sha256 ? asText(item.checksum_sha256) : null,
    last_error: item.last_error ? asText(item.last_error) : null,
  };
};

const normalizeInvoice = (payload: unknown): InvoiceDetail => {
  const item = (payload ?? {}) as Record<string, unknown>;
  const rawHeader = (item.header ?? {}) as Record<string, unknown>;
  if (!Array.isArray(item.line_items) || !Array.isArray(item.findings)) {
    throw new Error('API contract error: expected line_items and findings arrays.');
  }
  const lines = item.line_items;
  const findings = item.findings;

  return {
    id: asId(item.id),
    document_id: asId(item.document_id),
    buyer_oem_id: item.buyer_oem_id ? asText(item.buyer_oem_id) : null,
    processing_status: asStatus(item.processing_status, PROCESSING_STATUSES, 'processed'),
    validation_status: asStatus(item.validation_status, VALIDATION_STATUSES, 'pending'),
    review_status: asStatus(item.review_status, REVIEW_STATUSES, 'pending'),
    delivery_status: item.delivery_status == null ? undefined : asStatus(
      item.delivery_status,
      ['pending', 'ready', 'delivered', 'failed'] as const,
      'pending',
    ),
    header: {
      invoice_number: asText(rawHeader.invoice_number),
      invoice_date: rawHeader.invoice_date ? asText(rawHeader.invoice_date) : null,
      dealer_invoice_ref: rawHeader.dealer_invoice_ref
        ? asText(rawHeader.dealer_invoice_ref)
        : null,
      currency_code: asText(rawHeader.currency_code),
      subtotal_amount: requiredNumber(rawHeader.subtotal_amount, 'subtotal_amount'),
      discount_amount: requiredNumber(rawHeader.discount_amount, 'discount_amount'),
      tax_amount: requiredNumber(rawHeader.tax_amount, 'tax_amount'),
      total_amount: requiredNumber(rawHeader.total_amount, 'total_amount'),
    },
    line_items: lines.map(normalizeLine),
    findings: findings.map((finding, index) => normalizeFinding(finding, index)),
    updated_at: item.updated_at ? asText(item.updated_at) : null,
  };
};

const getArrayPayload = <T>(payload: unknown, mapper: (item: unknown) => T): T[] => {
  if (Array.isArray(payload)) {
    return payload.map(mapper);
  }

  if (payload && typeof payload === 'object') {
    const container = payload as Record<string, unknown>;
    if (Array.isArray(container.items)) {
      return container.items.map(mapper);
    }
    if (Array.isArray(container.data)) {
      return container.data.map(mapper);
    }
  }

  throw new Error('API contract error: expected an array or an items/data array envelope.');
};

export const getDocumentSource = async (documentId: Id, signal?: AbortSignal): Promise<Blob> => {
  asId(documentId);
  if (USE_DEV_MOCK_API) return getMockSource(documentId);
  const response = await api.get<Blob>(`/documents/${documentId}/source`, { responseType: 'blob', signal });
  return response.data;
};

export const getDocuments = async (
  filters: QueueFilters,
): Promise<DocumentQueueItem[]> => {
  if (USE_DEV_MOCK_API) {
    return getMockDocuments(filters);
  }

  const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value && value !== 'all'));
  const response = await api.get('/documents', { params });
  return getArrayPayload(response.data, normalizeDocument);
};

export const getDocument = async (documentId: Id): Promise<DocumentDetail> => {
  if (USE_DEV_MOCK_API) {
    return getMockDocument(documentId);
  }

  const response = await api.get(`/documents/${documentId}`);
  return normalizeDocumentDetail(response.data);
};

// Intake returns DocumentResponse, not the full document detail DTO.
const loadAcceptedDocument = async (payload: unknown): Promise<DocumentDetail> => {
  const acknowledgement = (payload ?? {}) as Record<string, unknown>;
  const documentId = asId(acknowledgement.id);
  try {
    return await getDocument(documentId);
  } catch {
    throw new Error(
      `Document #${documentId} was accepted, but its details could not be loaded. Open the queue; do not submit it again.`,
    );
  }
};

export const uploadDocument = async (
  payload: DocumentUploadPayload,
  onProgress?: (progress: number) => void,
): Promise<DocumentDetail> => {
  if (USE_DEV_MOCK_API) {
    return mockUploadDocument(payload);
  }

  const formData = new FormData();
  formData.append('dealer_id', payload.dealer_id);
  formData.append('dms_id', payload.dms_id);
  formData.append('source_type', payload.source_type);
  formData.append('file', payload.file);

  const response = await api.post('/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (onProgress && event.total) {
        const progress = Math.round((event.loaded / event.total) * 100);
        onProgress(progress);
      }
    },
  });

  return loadAcceptedDocument(response.data);
};

export const uploadDocumentJson = async (payload: {
  dealer_id: string;
  dms_id: string;
  payload: Record<string, unknown>;
}): Promise<DocumentDetail> => {
  if (USE_DEV_MOCK_API) {
    return mockUploadJson(payload);
  }

  const response = await api.post('/documents/json', payload);
  return loadAcceptedDocument(response.data);
};

export const processDocument = async (documentId: Id): Promise<DocumentDetail> => {
  if (USE_DEV_MOCK_API) {
    return mockProcessDocument(documentId);
  }

  const response = await api.post(`/documents/${documentId}/process`);
  return normalizeDocumentDetail(response.data);
};

export const getInvoices = async (): Promise<InvoiceDetail[]> => {
  if (USE_DEV_MOCK_API) {
    return getMockInvoices();
  }

  const response = await api.get('/invoices');
  return getArrayPayload(response.data, normalizeInvoice);
};

export const getInvoice = async (invoiceId: Id): Promise<InvoiceDetail> => {
  if (USE_DEV_MOCK_API) {
    return getMockInvoice(invoiceId);
  }

  const response = await api.get(`/invoices/${invoiceId}`);
  return normalizeInvoice(response.data);
};

export const patchInvoice = async (
  invoiceId: Id,
  payload: InvoicePatchPayload,
): Promise<InvoiceDetail> => {
  if (USE_DEV_MOCK_API) {
    return patchMockInvoice(invoiceId, payload);
  }

  const response = await api.patch(`/invoices/${invoiceId}`, payload);
  return normalizeInvoice(response.data);
};

export const reviewInvoice = async (
  invoiceId: Id,
  payload: InvoiceReviewPayload,
): Promise<InvoiceDetail> => {
  if (USE_DEV_MOCK_API) {
    return mockReviewInvoice(invoiceId, payload);
  }

  const response = await api.post(`/invoices/${invoiceId}/review`, payload);
  return normalizeInvoice(response.data);
};

const requireLiveRegistry = () => {
  if (USE_DEV_MOCK_API) throw new Error('DMS registry and mapping preview are unavailable in development fixture mode. Disable mock mode to use the real registry.');
};

export const getDealers = async (): Promise<DealerRegistryEntry[]> => {
  requireLiveRegistry();
  const response = await api.get<DealerRegistryEntry[]>('/dealers');
  return response.data;
};

export const getDmsSystems = async (): Promise<DmsRegistryEntry[]> => {
  requireLiveRegistry();
  const response = await api.get<DmsRegistryEntry[]>('/dms-systems');
  return response.data;
};

export const createDmsSystem = async (payload: CreateDmsPayload): Promise<DmsRegistryEntry> => {
  requireLiveRegistry();
  const response = await api.post<DmsRegistryEntry>('/dms-systems', payload);
  return response.data;
};

export const createDmsSystemBatch = async (payload: CreateDmsBatchPayload): Promise<DmsBatchRegistryResult> => {
  requireLiveRegistry();
  const response = await api.post<DmsBatchRegistryResult>('/dms-systems/batch', payload);
  return response.data;
};

export const previewDmsMapping = async (payload: MappingPreviewPayload): Promise<MappingPreviewResult> => {
  requireLiveRegistry();
  const response = await api.post<MappingPreviewResult>('/dms-systems/preview', payload);
  return response.data;
};

export const getApprovedInvoicePdf = async (invoiceId: Id): Promise<Blob> => {
  asId(invoiceId);
  if (USE_DEV_MOCK_API) throw new Error('Final invoice PDF download is unavailable in development fixture mode. No PDF is generated for a mock record.');
  const response = await api.get<Blob>(`/invoices/${invoiceId}/pdf`, { responseType: 'blob' });
  return response.data;
};

export default api;
