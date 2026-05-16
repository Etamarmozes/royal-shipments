import { api, apiBase } from "./client";
import type {
  Shipment, Container, ExtraWork, EmailUpdate, PendingShipment,
  DashboardKpis, ForecastWeek, ActionItem, Alert, ShipmentEvent, ListResponse,
  PalletBreakdown, PalletKpis, DailyForecastDay, ShipmentDocument, AIAnswer, AIContext,
} from "../types";

// ---------- Shipments ----------
export async function listShipments(params: Record<string, any> = {}): Promise<ListResponse<Shipment>> {
  const { data } = await api.get("/shipments", { params });
  return data;
}
export async function getShipment(id: number): Promise<Shipment> {
  const { data } = await api.get(`/shipments/${id}`);
  return data;
}
export async function createShipment(payload: Partial<Shipment>): Promise<Shipment> {
  const { data } = await api.post("/shipments", payload);
  return data;
}
export async function updateShipment(id: number, payload: Partial<Shipment>): Promise<Shipment> {
  const { data } = await api.put(`/shipments/${id}`, payload);
  return data;
}
export async function archiveShipment(id: number): Promise<Shipment> {
  const { data } = await api.delete(`/shipments/${id}`);
  return data;
}
export async function shipmentEvents(id: number): Promise<ShipmentEvent[]> {
  const { data } = await api.get(`/shipments/${id}/events`);
  return data;
}

// ---------- Containers ----------
export async function listContainers(params: Record<string, any> = {}): Promise<Container[]> {
  const { data } = await api.get("/containers", { params });
  return data;
}
export async function createContainer(payload: Partial<Container>): Promise<Container> {
  const { data } = await api.post("/containers", payload);
  return data;
}
export async function updateContainer(id: number, payload: Partial<Container>): Promise<Container> {
  const { data } = await api.put(`/containers/${id}`, payload);
  return data;
}
export async function deleteContainer(id: number): Promise<void> {
  await api.delete(`/containers/${id}`);
}
export async function getContainer(id: number): Promise<Container> {
  const { data } = await api.get(`/containers/${id}`);
  return data;
}
export async function calculatePallets(id: number): Promise<PalletBreakdown> {
  const { data } = await api.post(`/containers/${id}/calculate-pallets`);
  return data;
}

// ---------- Data Review (existing data: real vs demo) ----------
export interface DataReviewRow {
  id: number;
  shp_id: string;
  supplier: string | null;
  category: string | null;
  goods_description: string | null;
  current_stage: number | null;
  container_count: number;
  container_numbers: string[];
  creation_source: string | null;
  data_source: string | null;
  is_test_data: boolean;
  suspected_demo: boolean;
  demo_reasons: string[];
  created_at: string | null;
  updated_at: string | null;
  updated_by: string | null;
  last_update_source: string | null;
  archived: boolean;
}
export interface DataReviewResponse {
  summary: { total: number; suspected_demo: number; marked_test: number;
             archived: number; real: number; };
  rows: DataReviewRow[];
}
export async function listDataReview(): Promise<DataReviewResponse> {
  const { data } = await api.get("/data-review");
  return data;
}
export async function flagShipment(id: number, body: {
  is_test_data: boolean; data_source?: string; reason?: string;
}): Promise<{ id: number; shp_id: string; is_test_data: boolean; data_source: string | null }> {
  const { data } = await api.patch(`/data-review/${id}`, body);
  return data;
}
export async function bulkFlag(ids: number[], is_test_data: boolean,
                               data_source?: string): Promise<{ affected: number }> {
  const { data } = await api.patch(`/data-review/bulk-flag`,
    { ids, is_test_data, data_source });
  return data;
}
// ---------- Document Assignment QC (operational) ----------
export interface QcRow {
  id: number;
  document_id: number;
  filename: string | null;
  document_type: string | null;
  current_shipment_id: number | null;
  current_shp_id: string | null;
  current_supplier: string | null;
  suspected_shipment_id: number | null;
  suspected_shp_id: string | null;
  suspected_supplier: string | null;
  confidence_score: number;
  severity: "ok" | "minor" | "suspicious" | "strong_mismatch" | string;
  status: string;
  mismatch_reasons: string[];
  matched_signals: { rule: string; supplier: string; keyword: string; signal: string }[];
  recommendation: "keep" | "review" | "reassign_suggested" | "detach_suggested" | string;
  created_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_action: string | null;
}
export async function listQcDocuments(params: {
  status?: string; severity?: string;
} = {}): Promise<{ rows: QcRow[]; total: number }> {
  const { data } = await api.get("/qc/documents", { params });
  return data;
}
export async function qcSummary(): Promise<{
  open_total: number; open_strong_mismatch: number;
  open_suspicious: number; last_scan_at: string | null;
}> {
  const { data } = await api.get("/qc/summary");
  return data;
}
export async function runQcScan(): Promise<any> {
  const { data } = await api.post("/qc/documents/run");
  return data;
}
export async function qcApprove(resultId: number, body: {
  action: "keep" | "move" | "detach" | "mark_correct" | "needs_review" | "ignore";
  target_shipment_id?: number;
  reason?: string;
}): Promise<any> {
  const { data } = await api.post(`/qc/documents/${resultId}/approve`,
    { ...body, confirm: "APPLY" });
  return data;
}
export async function qcArchive(resultId: number, body: {
  mode: "archive_record_only" | "archive_file" | "delete_file";
  reason?: string;
}): Promise<any> {
  const confirm = body.mode === "delete_file" ? "DELETE" : "ARCHIVE";
  const { data } = await api.post(`/qc/documents/${resultId}/archive`,
    { ...body, confirm });
  return data;
}

// ---------- Shipment search (for QC reassign modal) ----------
export interface ShipmentSearchRow {
  id: number;
  shp_id: string;
  supplier: string | null;
  category: string | null;
  goods_description: string | null;
  po_number: string | null;
  bol_number: string | null;
  invoice_number: string | null;
  container_numbers: string[];
  eta_israel: string | null;
  eta_warehouse: string | null;
  stage_status: string | null;
  archived: boolean;
}
export async function searchShipments(q: string, limit = 20): Promise<{
  rows: ShipmentSearchRow[]; total: number;
}> {
  const { data } = await api.get("/shipments/search",
    { params: { q, limit } });
  return data;
}

// ---------- Document Assignment Review (diagnostic, kept for compat) ----------
export interface DocAssignmentRow {
  id: number;
  filename: string | null;
  linked_shipment_id: number | null;
  linked_shipment_shp_id: string | null;
  linked_container_id: number | null;
  linked_container_number: string | null;
  email_update_id: number | null;
  file_exists: boolean;
  suspected_wrong: boolean;
  suggested_shipment_id: number | null;
  suggested_shp_id: string | null;
  reasons: string[];
  confidence: number;
  action: "keep" | "needs_review";
  document_type: string | null;
}
export interface DocAssignmentResponse {
  summary: { total: number; linked: number; unassigned: number;
             suspected_wrong: number; missing_on_disk: number;
             needs_review: number; };
  rows: DocAssignmentRow[];
}
export async function listDocAssignmentReview(): Promise<DocAssignmentResponse> {
  const { data } = await api.get("/data-review/documents");
  return data;
}

export async function purgeTestData(): Promise<{ deleted: number; deleted_ids: any[] }> {
  const { data } = await api.post(`/data-review/purge-test-data`,
    { confirm: "DELETE", only_test_data: true });
  return data;
}

// ---------- Excel import ----------
export function importTemplateUrl(): string {
  return `${apiBase}/import/excel/template`;
}
export type MatchLevel =
  | "no_match"
  | "soft_possible_match"
  | "strong_possible_match"
  | "exact_duplicate";

export interface PossibleMatch {
  shipment_id: number;
  shipment_reference: string;
  supplier_name: string | null;
  category: string | null;
  eta_port: string | null;
  eta_warehouse?: string | null;
  status: string | null;
  match_score: number;
  match_reasons: string[];
}

export interface ImportPreviewRow {
  [k: string]: any;
  _row: number;
  _errors: string[];
  _match: { id: number; shp_id: string; matched_by: string } | null;
  _action_default: "create" | "update" | "skip" | "error";
  _action?: "create" | "update" | "skip";
  /** Set by the UI when the user overrides a strong/exact warning. */
  _force_create?: boolean;

  // Duplicate / similarity verdict — populated by /preview
  match_level?: MatchLevel;
  match_score?: number;
  match_reasons?: string[];
  matched_shipment_id?: number | null;
  matched_shipment_reference?: string | null;
  matched_shipment_supplier?: string | null;
  possible_matches?: PossibleMatch[];
}
export interface ImportPreview {
  file_errors: string[];
  rows: ImportPreviewRow[];
  summary: {
    total_rows: number; create: number; update: number; skip: number; error: number;
    needs_review?: number;
    exact_duplicate?: number;
    strong_match?: number;
    soft_match?: number;
    unique_suppliers: number; unique_containers: number;
  };
  /** Multi-format detection result. */
  format?: "royal_linen_template" | "icl" | "eli_line" | "unknown" | string;
  format_info?: {
    sheet_name?: string;
    header_row?: number;
    source_provider?: string;
    notes?: string;
  };
  /** When false, the apply button must be disabled — only Royal Linen
   *  template is currently apply-eligible. */
  applyable?: boolean;
}
export async function previewExcelImport(file: File): Promise<ImportPreview> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post("/import/excel/preview", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
export interface ApplyResultExternal {
  batch_id: number;
  source_provider: string;
  created: number;
  updated: number;
  skipped: number;
  containers_added: number;
  errors: number;
  per_row: Array<{
    source_row_number: number;
    external_ref: string | null;
    action_requested: string;
    action_taken: string;
    shp_id: string | null;
    shipment_id: number | null;
    containers_added: number;
    error: string | null;
  }>;
}
export interface ApplyResultTemplate {
  created_shipments: number; updated_shipments: number;
  added_containers: number; updated_containers: number;
  skipped: number; details: string[];
}
export async function applyExcelImport(
  rows: ImportPreviewRow[]
): Promise<ApplyResultTemplate | ApplyResultExternal> {
  const { data } = await api.post("/import/excel/apply",
    { rows, confirm: "APPLY" });
  return data;
}

// ---------- Import batches (rollback) ----------
export interface ImportBatchSummary {
  id: number;
  source_provider: string;
  source_file_name: string | null;
  source_sheet_name: string | null;
  imported_by: string | null;
  imported_at: string | null;
  total_rows_in_preview: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  error_count: number;
  status: string;
  rolled_back_at: string | null;
  rolled_back_by: string | null;
  rolled_back_count: number;
  notes: string | null;
}
export interface ImportBatchDetail extends ImportBatchSummary {
  rolled_back_reason: string | null;
  details: any;
  live_shipments: Array<{
    id: number; shp_id: string; supplier: string | null;
    had_post_import_edits: boolean;
  }>;
}
export async function listImportBatches(): Promise<ImportBatchSummary[]> {
  const { data } = await api.get("/import/batches");
  return data;
}
export async function getImportBatch(id: number): Promise<ImportBatchDetail> {
  const { data } = await api.get(`/import/batches/${id}`);
  return data;
}
export async function rollbackImportBatch(id: number, reason: string): Promise<{
  batch_id: number;
  archived_count: number;
  had_edits_count: number;
  archived_shipments: { id: number; shp_id: string; had_post_import_edits: boolean }[];
}> {
  const { data } = await api.post(`/import/batches/${id}/rollback`,
    { confirm: "ROLLBACK", reason });
  return data;
}

// ---------- Data quality ----------
export interface DataQuality {
  entity_type: "shipment" | "container";
  entity_id: number;
  score: "complete" | "missing_minor" | "missing_critical";
  missing_critical: { field: string; label: string }[];
  missing_minor: { field: string; label: string }[];
  missing_count: number;
}
export async function shipmentDataQuality(id: number): Promise<DataQuality> {
  const { data } = await api.get(`/shipments/${id}/data-quality`);
  return data;
}
export async function containerDataQuality(id: number): Promise<DataQuality> {
  const { data } = await api.get(`/containers/${id}/data-quality`);
  return data;
}
export async function getPalletBreakdown(id: number): Promise<PalletBreakdown> {
  const { data } = await api.get(`/containers/${id}/pallet-breakdown`);
  return data;
}

// ---------- Extra Work ----------
export async function listExtraWork(params: Record<string, any> = {}): Promise<ExtraWork[]> {
  const { data } = await api.get("/extra-work", { params });
  return data;
}
export async function createExtraWork(payload: Partial<ExtraWork>): Promise<ExtraWork> {
  const { data } = await api.post("/extra-work", payload);
  return data;
}
export async function updateExtraWork(id: number, payload: Partial<ExtraWork>): Promise<ExtraWork> {
  const { data } = await api.put(`/extra-work/${id}`, payload);
  return data;
}
export async function completeExtraWork(id: number): Promise<ExtraWork> {
  const { data } = await api.put(`/extra-work/${id}/complete`);
  return data;
}

// ---------- Email ----------
export async function syncEmailNow(): Promise<{ synced_at: string; message: string }> {
  const { data } = await api.post("/email/sync-now");
  return data;
}
export async function processFetchedEmails(): Promise<{
  processed: number; update: number; delay: number; new_shipment: number; unknown: number; errors: number;
}> {
  const { data } = await api.post("/email/process-fetched");
  return data;
}
export async function reprocessEmail(id: number): Promise<EmailUpdate> {
  const { data } = await api.put(`/email/updates/${id}/reprocess`);
  return data;
}

// ---------- Gmail ----------
export interface GmailStatus {
  connected: boolean;
  token_file_exists: boolean;
  credentials_file_exists: boolean;
  expiry?: string | null;
  scopes: string[];
  /** True when the operator has set GMAIL_DISABLED=true in env. */
  disabled?: boolean;
  /** Hebrew explanation when disabled — surface this in the UI. */
  disabled_reason?: string;
}
export async function gmailStatus(): Promise<GmailStatus> {
  const { data } = await api.get("/gmail/status");
  return data;
}
export async function gmailSync(): Promise<{ matched: number; inserted: number; skipped_existing: number; errors: any[] }> {
  const { data } = await api.post("/gmail/sync");
  return data;
}
export async function gmailDisconnect(): Promise<{ ok: boolean; message: string }> {
  const { data } = await api.post("/gmail/disconnect");
  return data;
}
/**
 * Build the absolute /gmail/connect URL for the current environment.
 * In dev (apiBase = "/api"), the Vite proxy sends /api/* to the backend, but
 * the OAuth redirect needs to reach the *raw* backend host. We compute that
 * by stripping "/api" from apiBase, or fall back to the current origin's
 * port-8000 sibling.
 */
export function gmailConnectUrl(): string {
  const fromEnv = import.meta.env.VITE_BACKEND_URL as string | undefined;
  if (fromEnv) return `${fromEnv.replace(/\/$/, "")}/gmail/connect`;
  // /api → empty (same origin) but use port 8000 for the dev case
  if (apiBase === "/api" && typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000/gmail/connect`;
  }
  return `${apiBase.replace(/\/api$/, "")}/gmail/connect`;
}

// ---------- Unified Pending ----------
export interface PendingItem {
  kind: "update" | "shipment";
  id: number;
  detection_type: string;
  confidence_score: number | null;
  status: string;
  sender?: string | null;
  subject?: string | null;
  received_at?: string | null;
  body_excerpt?: string | null;
  summary?: string | null;
  extracted_fields: Record<string, any>;
  shipment_id?: number | null;
  shp_id?: string | null;
  container_count?: number;
  created_at?: string | null;
  raw?: Record<string, any>;
}
export async function listPending(): Promise<{ items: PendingItem[]; counts: { total: number; updates: number; shipments: number } }> {
  const { data } = await api.get("/pending");
  return data;
}
export async function approvePending(kind: "update" | "shipment", id: number): Promise<any> {
  const { data } = await api.post(`/pending/${kind}/${id}/approve`);
  return data;
}
export async function rejectPending(kind: "update" | "shipment", id: number, note?: string): Promise<any> {
  const params = new URLSearchParams();
  if (note) params.set("note", note);
  const { data } = await api.post(`/pending/${kind}/${id}/reject?${params.toString()}`);
  return data;
}
export async function injectEmail(payload: {
  sender: string; subject: string; body: string;
  attachment_names?: string[];
}): Promise<EmailUpdate> {
  const { data } = await api.post("/email/inject", payload);
  return data;
}
export async function listEmailUpdates(params: Record<string, any> = {}): Promise<EmailUpdate[]> {
  const { data } = await api.get("/email/updates", { params });
  return data;
}
export async function approveEmailUpdate(id: number, approved_by = "admin"): Promise<EmailUpdate> {
  const { data } = await api.put(`/email/updates/${id}/approve`, { approved_by });
  return data;
}
export async function rejectEmailUpdate(id: number, approved_by = "admin"): Promise<EmailUpdate> {
  const { data } = await api.put(`/email/updates/${id}/reject`, { approved_by });
  return data;
}
export async function assignEmailUpdate(id: number, shipment_id: number): Promise<EmailUpdate> {
  const { data } = await api.put(`/email/updates/${id}/assign-shipment`, { shipment_id });
  return data;
}

// ---------- Pending Shipments ----------
export async function listPendingShipments(status = "pending"): Promise<PendingShipment[]> {
  const { data } = await api.get("/pending-shipments", { params: { status } });
  return data;
}
export async function getPendingShipment(id: number): Promise<PendingShipment> {
  const { data } = await api.get(`/pending-shipments/${id}`);
  return data;
}
export async function updatePendingShipment(id: number, payload: Partial<PendingShipment>): Promise<PendingShipment> {
  const { data } = await api.put(`/pending-shipments/${id}`, payload);
  return data;
}
export async function approvePendingShipment(id: number): Promise<Shipment> {
  const { data } = await api.post(`/pending-shipments/${id}/approve`, { approved_by: "admin" });
  return data;
}
export async function rejectPendingShipment(id: number, note?: string): Promise<PendingShipment> {
  const { data } = await api.post(`/pending-shipments/${id}/reject`, { approved_by: "admin", note });
  return data;
}
export async function assignPendingToShipment(id: number, shipment_id: number): Promise<PendingShipment> {
  const { data } = await api.post(`/pending-shipments/${id}/assign-to-existing-shipment`, {
    shipment_id, approved_by: "admin",
  });
  return data;
}

// ---------- Dashboard ----------
export async function dashboardKpis(): Promise<DashboardKpis> {
  const { data } = await api.get("/dashboard/kpis");
  return data;
}
export async function dashboardForecast(): Promise<ForecastWeek[]> {
  const { data } = await api.get("/dashboard/forecast-8-weeks");
  return data;
}
export async function dashboardActionItems(): Promise<ActionItem[]> {
  const { data } = await api.get("/dashboard/action-items");
  return data;
}
export async function dashboardPalletKpis(): Promise<PalletKpis> {
  const { data } = await api.get("/dashboard/pallet-kpis");
  return data;
}
export async function dashboardPalletForecastDaily(days = 14): Promise<DailyForecastDay[]> {
  const { data } = await api.get("/dashboard/pallet-forecast-daily", { params: { days } });
  return data;
}

// ---------- Shipment product image ----------
/**
 * @deprecated DO NOT use as `<img src>` — the browser won't include the JWT.
 * Use the `<AuthedImage path={...} />` component instead.
 */
export function shipmentProductImageUrl(shipmentId: number, cacheBuster?: string): string {
  const cb = cacheBuster ? `?v=${encodeURIComponent(cacheBuster)}` : "";
  return `${apiBase}/shipments/${shipmentId}/product-image${cb}`;
}
export async function uploadShipmentProductImage(shipmentId: number, file: File): Promise<{ ok: boolean; product_image_path: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post(`/shipments/${shipmentId}/product-image`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
export async function deleteShipmentProductImage(shipmentId: number): Promise<{ ok: boolean }> {
  const { data } = await api.delete(`/shipments/${shipmentId}/product-image`);
  return data;
}

// ---------- Categories ----------
export async function listCategories(): Promise<{ categories: string[] }> {
  const { data } = await api.get("/shipments/categories/list");
  return data;
}

// ---------- Document Intelligence (classification + smart status) ----------
export type DocumentClassification =
  | "shipment_document"
  | "commercial_invoice"
  | "packing_list"
  | "bill_of_lading"
  | "house_bill_of_lading"
  | "master_bill_of_lading"
  | "purchase_order"
  | "customs_document"
  | "delivery_note"
  | "certificate"
  | "product_image"
  | "email_noise"
  | "unknown_needs_review";

export interface SmartDocStatus {
  shipment_id: number;
  shp_id: string;
  by_type: Record<"invoice" | "packing_list" | "bl", {
    required_type: string;
    status: "missing" | "document_exists" | "data_extracted" | "needs_review" | "approved";
    label_he: string;
    documents: Array<{
      id: number;
      filename: string | null;
      classification: string | null;
      classification_confidence: number | null;
      manually_set: boolean;
    }>;
    shipment_field_value: string | null;
  }>;
  summary: { missing: number; document_exists: number; data_extracted: number };
  other_documents: Array<{
    id: number;
    filename: string | null;
    classification: string | null;
    classification_confidence: number | null;
  }>;
  noise_filtered_count: number;
  real_documents_count: number;
  // legacy compat fields
  present?: string[];
  missing?: string[];
  is_complete?: boolean;
  count?: number;
}

export async function getSmartDocStatus(shipmentId: number): Promise<SmartDocStatus> {
  const { data } = await api.get(`/documents/required-status/${shipmentId}`);
  return data;
}
export async function recalculateDocStatus(shipmentId: number): Promise<SmartDocStatus & { rescanned: number }> {
  const { data } = await api.post(`/shipments/${shipmentId}/recalculate-document-status`);
  return data;
}
export async function classifyDocument(docId: number): Promise<{
  id: number; classification: string; classification_confidence: number;
  classification_reason: string; is_email_noise: boolean;
  manually_classified_by: string | null;
}> {
  const { data } = await api.post(`/documents/${docId}/classify`);
  return data;
}
export async function setDocumentType(docId: number, classification: DocumentClassification, reason?: string) {
  const { data } = await api.post(`/documents/${docId}/set-type`,
    { classification, reason });
  return data;
}
export async function markDocAsNoise(docId: number) {
  const { data } = await api.post(`/documents/${docId}/mark-noise`);
  return data;
}
export async function restoreDocAsDocument(docId: number) {
  const { data } = await api.post(`/documents/${docId}/restore-as-document`);
  return data;
}
export async function listFilteredNoise(): Promise<any[]> {
  const { data } = await api.get(`/documents/filtered-noise`);
  return data;
}
export async function classifyAllDocuments(): Promise<{
  total: number; classified: number; skipped_manual: number;
}> {
  const { data } = await api.post(`/documents/classify-all`);
  return data;
}

// ---------- Documents ----------
export async function listDocuments(params: Record<string, any> = {}): Promise<ShipmentDocument[]> {
  const { data } = await api.get("/documents", { params });
  return data;
}
/**
 * Scoped per-shipment document fetch.
 * Returns only docs linked to this shipment OR via its containers.
 * Always prefer this over `listDocuments({ shipment_id })` on shipment pages.
 */
export async function listShipmentDocuments(shipmentId: number): Promise<ShipmentDocument[]> {
  const { data } = await api.get(`/shipments/${shipmentId}/documents`);
  return data;
}
/**
 * @deprecated DO NOT use as `<a href>` or `<img src>` — the browser won't
 * include the JWT and the backend will return 401. Use
 * `downloadDocument()` from `utils/fileAccess` instead.
 */
export function documentDownloadUrl(docId: number): string {
  return `${apiBase}/documents/${docId}/download`;
}
export async function assignDocument(
  docId: number, shipmentId?: number, containerId?: number,
): Promise<ShipmentDocument> {
  const params: Record<string, number> = {};
  if (shipmentId !== undefined) params.shipment_id = shipmentId;
  if (containerId !== undefined) params.container_id = containerId;
  const { data } = await api.put(`/documents/${docId}/assign`, null, { params });
  return data;
}
export async function changeDocumentType(docId: number, document_type: string): Promise<ShipmentDocument> {
  const { data } = await api.put(`/documents/${docId}/document-type`, null, { params: { document_type } });
  return data;
}
export async function uploadDocument(
  file: File, shipmentId?: number, containerId?: number, documentType?: string,
): Promise<ShipmentDocument> {
  const fd = new FormData();
  fd.append("file", file);
  if (shipmentId !== undefined) fd.append("shipment_id", String(shipmentId));
  if (containerId !== undefined) fd.append("container_id", String(containerId));
  if (documentType) fd.append("document_type", documentType);
  const { data } = await api.post("/documents/upload", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
export async function requiredDocumentsStatus(shipmentId: number): Promise<{
  present: string[]; missing: string[]; is_complete: boolean; count: number;
}> {
  const { data } = await api.get(`/documents/required-status/${shipmentId}`);
  return data;
}
/**
 * @deprecated DO NOT use as `<a href>` or `<img src>` — the browser won't
 * include the JWT and the backend will return 401. Use `viewDocument()`
 * from `utils/fileAccess` instead.
 */
export function documentPreviewUrl(docId: number): string {
  return `${apiBase}/documents/${docId}/preview`;
}
export async function autoLinkDocuments(): Promise<{ scanned: number; linked: number; still_unassigned: number }> {
  const { data } = await api.post("/documents/auto-link");
  return data;
}
export async function backfillGmailAttachments(): Promise<{ scanned: number; downloaded: number; linked: number; ok: boolean; message?: string }> {
  const { data } = await api.post("/gmail/backfill-attachments");
  return data;
}
export async function possibleMatches(docId: number): Promise<{
  document_id: number; filename: string;
  candidates: { shipment_id: number; shp_id: string; supplier: string; score: number }[];
}> {
  const { data } = await api.get(`/documents/${docId}/possible-matches`);
  return data;
}

export interface FileStatus {
  id: number;
  status: "valid" | "missing" | "empty" | "drive_link" | "no_file";
  size: number | null;
  signature: "pdf" | "ooxml" | "ole" | "image_jpeg" | "image_png" | "image_gif" | "unknown" | null;
}
export async function fileStatus(docId: number): Promise<FileStatus> {
  const { data } = await api.get(`/documents/${docId}/file-status`);
  return data;
}

export interface ExcelSheet {
  name: string;
  rows: any[][];
  row_count: number;
  col_count: number;
  truncated: boolean;
}
export interface ExcelPreviewData {
  id: number;
  filename: string;
  size: number;
  format?: "xlsx" | "xls";
  sheets?: ExcelSheet[];
  error?: string;
}
export async function excelPreview(docId: number): Promise<ExcelPreviewData> {
  const { data } = await api.get(`/documents/${docId}/excel-preview`);
  return data;
}

export async function redownloadDocument(docId: number): Promise<any> {
  const { data } = await api.post(`/documents/${docId}/redownload`);
  return data;
}
export async function redownloadInvalidDocuments(): Promise<{ fixed: number; skipped_ok: number; failed: any[] }> {
  const { data } = await api.post("/documents/redownload-invalid");
  return data;
}

// ---------- Receiving ----------
export async function receivingQueue(): Promise<any[]> {
  const { data } = await api.get("/receiving/queue");
  return data;
}
export async function getReceivingView(containerId: number): Promise<any> {
  const { data } = await api.get(`/receiving/container/${containerId}`);
  return data;
}
export async function receiveContainer(
  containerId: number,
  payload: {
    received_cartons_actual?: number | null;
    received_pallets_actual?: number | null;
    received_notes?: string | null;
    received_by?: string;
    receiving_status?: string;
  },
): Promise<Container> {
  const { data } = await api.post(`/receiving/container/${containerId}/receive`, payload);
  return data;
}

// ---------- AI ----------
export async function aiAsk(question: string, context?: AIContext): Promise<AIAnswer> {
  const { data } = await api.post("/ai/ask", { question, context });
  return data;
}
export async function aiSuggestions(context?: AIContext): Promise<{ questions: string[] }> {
  const { data } = await api.get("/ai/suggestions", { params: context });
  return data;
}

// ---------- Alerts ----------
export async function listAlerts(params: Record<string, any> = {}): Promise<Alert[]> {
  const { data } = await api.get("/alerts", { params });
  return data;
}
export async function resolveAlert(id: number): Promise<Alert> {
  const { data } = await api.put(`/alerts/${id}/resolve`);
  return data;
}
export async function scanAlerts(): Promise<{ ok: boolean }> {
  const { data } = await api.post("/alerts/scan");
  return data;
}

// ---------- Export ----------
export function exportExcelUrl(): string {
  return `${apiBase}/export/excel`;
}

// ---------- Auth ----------
import type { AuthUser } from "../auth/store";

export async function authLogin(username: string, password: string): Promise<{ access_token: string; user: AuthUser }> {
  const { data } = await api.post("/auth/login", { username, password });
  return data;
}
export async function authMe(): Promise<AuthUser> {
  const { data } = await api.get("/auth/me");
  return data;
}
export async function authLogout(): Promise<void> {
  try { await api.post("/auth/logout"); } catch {}
}
export async function authChangePassword(current_password: string, new_password: string): Promise<void> {
  await api.post("/auth/change-password", { current_password, new_password });
}

// ---------- Users management (admin only) ----------
export async function listUsers(): Promise<any[]> {
  const { data } = await api.get("/users");
  return data;
}
export async function listRoles(): Promise<{ roles: { id: string; label: string }[] }> {
  const { data } = await api.get("/users/roles/list");
  return data;
}
export async function createUserApi(payload: {
  username: string; full_name: string; password: string;
  role: string; email?: string; phone?: string; must_change_password?: boolean;
}): Promise<any> {
  const { data } = await api.post("/users", payload);
  return data;
}
export async function updateUserApi(id: number, payload: {
  full_name?: string; role?: string; email?: string; phone?: string; is_active?: boolean;
}): Promise<any> {
  const { data } = await api.put(`/users/${id}`, payload);
  return data;
}
export async function resetUserPassword(id: number, newPassword: string, mustChange = true): Promise<void> {
  await api.post(`/users/${id}/reset-password`, {
    new_password: newPassword, must_change_password: mustChange,
  });
}
