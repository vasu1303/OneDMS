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

const delay = (ms = 350) => new Promise((resolve) => setTimeout(resolve, ms));

const now = new Date();

// Only retain actual submissions; seeded records have no original file.
const mockSources = new Map<Id, Blob>();
export const getMockSource = async (documentId: Id): Promise<Blob> => {
  await delay();
  const source = mockSources.get(documentId);
  if (!source) throw new Error('This seeded development fixture has no retained original. Upload a file or JSON in fixture mode to inspect its actual source.');
  return source;
};

let mockDocuments: DocumentDetail[] = [
  {
    id: 104,
    dealer_code: 'D-4512',
    dealer_name: 'Bangalore Commercial Vehicles',
    dms_name: 'DealerSoft Pro',
    source_type: 'pdf',
    source_filename: 'invoice-104.pdf',
    received_at: new Date(now.getTime() - 1000 * 60 * 48).toISOString(),
    processing_status: 'review_required',
    validation_status: 'warning',
    review_status: 'in_review',
    summary: 'Header extracted. Two line item fields need confirmation.',
    has_findings: true,
    findings_count: 2,
    invoice_id: 1004,
    source_content_type: 'application/pdf',
    source_size_bytes: 142000,
    checksum_sha256: 'mock-104',
    last_error: null,
  },
  {
    id: 107,
    dealer_code: 'D-8871',
    dealer_name: 'North Fleet Hub',
    dms_name: 'RoadLedger',
    source_type: 'json',
    source_filename: 'invoice-107.json',
    received_at: new Date(now.getTime() - 1000 * 60 * 12).toISOString(),
    processing_status: 'failed',
    validation_status: 'invalid',
    review_status: 'pending',
    summary: 'Could not reconcile totals from submitted payload.',
    has_findings: true,
    findings_count: 3,
    invoice_id: null,
    source_content_type: 'application/json',
    source_size_bytes: 9700,
    checksum_sha256: 'mock-107',
    last_error: 'Invoice total mismatch between header and computed lines.',
  },
  {
    id: 110,
    dealer_code: 'D-9902',
    dealer_name: 'Highway Equipment',
    dms_name: 'FleetBridge',
    source_type: 'excel',
    source_filename: 'invoice-110.xlsx',
    received_at: new Date(now.getTime() - 1000 * 60 * 5).toISOString(),
    processing_status: 'processing',
    validation_status: 'pending',
    review_status: 'pending',
    summary: 'Extraction worker started.',
    has_findings: false,
    findings_count: 0,
    invoice_id: null,
    source_content_type:
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    source_size_bytes: 34220,
    checksum_sha256: 'mock-110',
    last_error: null,
  },
];

let mockInvoices: InvoiceDetail[] = [
  {
    id: 1004,
    document_id: 104,
    buyer_oem_id: 'DT-IND',
    processing_status: 'processed',
    validation_status: 'warning',
    review_status: 'in_review',
    delivery_status: 'pending',
    header: {
      invoice_number: 'INV-104-2026',
      invoice_date: '2026-10-09',
      dealer_invoice_ref: 'DLR-104',
      currency_code: 'INR',
      subtotal_amount: 162500,
      discount_amount: 2500,
      tax_amount: 28800,
      total_amount: 188800,
    },
    line_items: [
      {
        id: 1,
        line_number: 1,
        part_number: 'A-222',
        description: 'Front axle assembly',
        quantity: 2,
        unit_price: 48000,
        discount_amount: 0,
        tax_amount: 17280,
        line_total: 113280,
        vin: null,
      },
      {
        id: 2,
        line_number: 2,
        part_number: 'S-991',
        description: 'Suspension kit',
        quantity: 1,
        unit_price: 66500,
        discount_amount: 2500,
        tax_amount: 11520,
        line_total: 75520,
        vin: null,
      },
    ],
    findings: [
      {
        id: 1,
        severity: 'warning',
        field: 'line_items[2].part_number',
        line_number: 2,
        message: 'Character confidence is low on part number.',
        confidence: 0.78,
        extracted_value: 'S-99?',
        approved_value: 'S-991',
      },
      {
        id: 2,
        severity: 'info',
        field: 'header.dealer_invoice_ref',
        line_number: null,
        message: 'Dealer reference inferred from stamp block.',
        confidence: 0.84,
        extracted_value: 'DLR 104',
        approved_value: 'DLR-104',
      },
    ],
    updated_at: now.toISOString(),
  },
];

const queueMatch = (document: DocumentQueueItem, filters: QueueFilters): boolean => {
  const processingFilter = filters.processing_status;
  if (processingFilter && processingFilter !== 'all') {
    if (document.processing_status !== processingFilter) {
      return false;
    }
  }

  const validationFilter = filters.validation_status;
  if (validationFilter && validationFilter !== 'all') {
    if (document.validation_status !== validationFilter) {
      return false;
    }
  }

  const reviewFilter = filters.review_status;
  if (reviewFilter && reviewFilter !== 'all') {
    if (document.review_status !== reviewFilter) {
      return false;
    }
  }

  const dealerFilter = filters.dealer_code?.trim().toLowerCase();
  if (dealerFilter && !document.dealer_code.toLowerCase().includes(dealerFilter)) {
    return false;
  }

  const q = filters.q?.trim().toLowerCase();
  if (q) {
    const haystack = [
      document.dealer_code,
      document.dealer_name,
      document.dms_name,
      document.source_filename,
      document.summary,
      String(document.id),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    if (!haystack.includes(q)) {
      return false;
    }
  }

  return true;
};

export const getMockDocuments = async (
  filters: QueueFilters,
): Promise<DocumentQueueItem[]> => {
  await delay();
  return mockDocuments.filter((item) => queueMatch(item, filters));
};

export const getMockDocument = async (documentId: Id): Promise<DocumentDetail> => {
  await delay();
  const document = mockDocuments.find((item) => item.id === documentId);
  if (!document) {
    throw new Error('Document not found in mock mode');
  }

  return document;
};

export const mockUploadDocument = async (
  payload: DocumentUploadPayload,
): Promise<DocumentDetail> => {
  await delay(700);

  const id = Math.max(...mockDocuments.map((item) => item.id)) + 1;
  const uploaded: DocumentDetail = {
    id,
    dealer_code: payload.dealer_id,
    dealer_name: payload.dealer_id,
    dms_name: payload.dms_id,
    source_type: payload.source_type,
    source_filename: payload.file.name,
    received_at: new Date().toISOString(),
    processing_status: 'received',
    validation_status: 'pending',
    review_status: 'pending',
    summary: 'Document accepted and queued.',
    has_findings: false,
    findings_count: 0,
    invoice_id: null,
    source_content_type: payload.file.type,
    source_size_bytes: payload.file.size,
    checksum_sha256: `mock-${id}`,
    last_error: null,
  };

  mockDocuments = [uploaded, ...mockDocuments];
  mockSources.set(id, payload.file);
  return uploaded;
};

export const mockUploadJson = async (payload: {
  dealer_id: string;
  dms_id: string;
  payload: Record<string, unknown>;
}): Promise<DocumentDetail> => {
  await delay(500);
  const id = Math.max(...mockDocuments.map((item) => item.id)) + 1;

  const uploaded: DocumentDetail = {
    id,
    dealer_code: payload.dealer_id,
    dealer_name: payload.dealer_id,
    dms_name: payload.dms_id,
    source_type: 'json',
    source_filename: `submission-${id}.json`,
    received_at: new Date().toISOString(),
    processing_status: 'received',
    validation_status: 'pending',
    review_status: 'pending',
    summary: 'JSON payload accepted and queued.',
    has_findings: false,
    findings_count: 0,
    invoice_id: null,
    source_content_type: 'application/json',
    source_size_bytes: JSON.stringify(payload.payload).length,
    checksum_sha256: `mock-${id}`,
    last_error: null,
  };

  mockDocuments = [uploaded, ...mockDocuments];
  mockSources.set(id, new Blob([JSON.stringify(payload.payload, null, 2)], { type: 'application/json' }));
  return uploaded;
};

export const mockProcessDocument = async (documentId: Id): Promise<DocumentDetail> => {
  await delay(1000);
  const target = mockDocuments.find((item) => item.id === documentId);
  if (!target) {
    throw new Error('Document not found in mock mode');
  }

  target.processing_status = 'review_required';
  target.validation_status = 'warning';
  target.review_status = 'in_review';

  if (!target.invoice_id) {
    const invoiceId = Math.max(...mockInvoices.map((item) => item.id)) + 1;
    target.invoice_id = invoiceId;
    mockInvoices = [
      {
        id: invoiceId,
        document_id: target.id,
        buyer_oem_id: 'DT-IND',
        processing_status: 'processed',
        validation_status: 'warning',
        review_status: 'in_review',
        delivery_status: 'pending',
        header: {
          invoice_number: `INV-${target.id}-POC`,
          invoice_date: new Date().toISOString().slice(0, 10),
          dealer_invoice_ref: null,
          currency_code: 'INR',
          subtotal_amount: 0,
          discount_amount: 0,
          tax_amount: 0,
          total_amount: 0,
        },
        line_items: [
          {
            line_number: 1,
            quantity: 0,
            unit_price: 0,
            discount_amount: 0,
            tax_amount: 0,
            line_total: 0,
          },
        ],
        findings: [
          {
            severity: 'warning',
            field: 'header.total_amount',
            message: 'Total amount requires manual confirmation.',
            line_number: null,
            confidence: 0.61,
          },
        ],
      },
      ...mockInvoices,
    ];
  }

  return target;
};

export const getMockInvoices = async (): Promise<InvoiceDetail[]> => {
  await delay();
  return mockInvoices;
};

export const getMockInvoice = async (invoiceId: Id): Promise<InvoiceDetail> => {
  await delay();
  const invoice = mockInvoices.find((item) => item.id === invoiceId);
  if (!invoice) {
    throw new Error('Invoice not found in mock mode');
  }

  return invoice;
};

export const patchMockInvoice = async (
  invoiceId: Id,
  payload: InvoicePatchPayload,
): Promise<InvoiceDetail> => {
  await delay(400);
  const invoice = mockInvoices.find((item) => item.id === invoiceId);
  if (!invoice) {
    throw new Error('Invoice not found in mock mode');
  }

  if (payload.header) {
    invoice.header = { ...invoice.header, ...payload.header };
  }

  if (payload.line_items?.length) {
    invoice.line_items = invoice.line_items.map((line) => {
      const patch = payload.line_items?.find(
        (candidate) => candidate.line_number === line.line_number,
      );
      return patch ? { ...line, ...patch } : line;
    });
  }

  invoice.updated_at = new Date().toISOString();
  return invoice;
};

export const mockReviewInvoice = async (
  invoiceId: Id,
  payload: InvoiceReviewPayload,
): Promise<InvoiceDetail> => {
  await delay(450);
  const invoice = mockInvoices.find((item) => item.id === invoiceId);
  if (!invoice) {
    throw new Error('Invoice not found in mock mode');
  }

  invoice.review_status = payload.decision === 'approve' ? 'approved' : 'rejected';
  invoice.validation_status = payload.decision === 'approve' ? 'valid' : 'invalid';
  invoice.delivery_status = payload.decision === 'approve' ? 'ready' : 'failed';

  const document = mockDocuments.find((item) => item.id === invoice.document_id);
  if (document) {
    document.review_status = invoice.review_status;
    document.validation_status = invoice.validation_status;
    document.processing_status =
      payload.decision === 'approve' ? 'processed' : 'review_required';
    document.summary =
      payload.decision === 'approve'
        ? 'Invoice approved and marked ready for delivery.'
        : 'Invoice rejected during reviewer decision.';
  }

  invoice.updated_at = new Date().toISOString();
  return invoice;
};
