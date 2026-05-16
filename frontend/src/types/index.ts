export interface Shipment {
  id: number;
  shp_id: string;
  supplier?: string | null;
  goods_description?: string | null;
  origin_country?: string | null;
  origin_port?: string | null;
  shipping_channel?: string | null;
  current_stage?: number | null;
  stage_status?: string | null;
  order_date?: string | null;
  created_date?: string | null;
  etd?: string | null;
  eta_israel?: string | null;
  eta_port?: string | null;
  eta_warehouse?: string | null;
  actual_arrival_israel?: string | null;
  actual_arrival_port?: string | null;
  actual_arrival_warehouse?: string | null;
  days_to_arrival?: number | null;
  customs_broker?: string | null;
  booking_number?: string | null;
  bol_number?: string | null;
  invoice_number?: string | null;
  po_number?: string | null;
  freight_price_usd?: number | null;
  goods_value_usd?: number | null;
  paperwork_complete?: boolean | null;
  approval_status?: string | null;
  delay_status?: boolean | null;
  delay_reason?: string | null;
  notes?: string | null;
  creation_source?: string | null;
  last_update_source?: string | null;
  archived?: boolean;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
  extra_work_required?: boolean | null;
  extra_work_note?: string | null;
  extra_work_defined_at?: string | null;
  extra_work_defined_by?: string | null;
  container_count?: number;
  has_open_extra_work?: boolean;
  product_image_path?: string | null;
  last_auto_update_source_email_id?: number | null;
  last_auto_update_at?: string | null;
  category?: string | null;
  category_source?: string | null;
  /** Per-field manual-override metadata: { field: { by, at } } */
  manual_overrides?: Record<string, { by?: string; at?: string }> | null;
}

export interface ShipmentDocument {
  id: number;
  email_update_id?: number | null;
  filename?: string | null;
  file_type?: string | null;
  file_size?: number | null;
  file_path?: string | null;
  document_type?: string | null;
  gmail_attachment_id?: string | null;
  drive_file_id?: string | null;
  source_url?: string | null;
  linked_shipment_id?: number | null;
  linked_container_id?: number | null;
  uploaded_at?: string | null;
  source_email_sender?: string | null;
  source_email_subject?: string | null;
  received_at?: string | null;
  shp_id?: string | null;
  supplier?: string | null;
  container_number?: string | null;
  // Document Intelligence
  classification?: string | null;
  classification_confidence?: number | null;
  classification_reason?: string | null;
  is_email_noise?: boolean | null;
  manually_classified_by?: string | null;
}

export interface AISource {
  kind: string;
  id: number;
  label: string;
  link?: string | null;
}

export interface AIAnswer {
  answer: string;
  intent: string;
  confidence: "high" | "medium" | "low";
  sources: AISource[];
  actions?: { label: string; link: string }[];
}

export interface AIContext {
  shipment_id?: number;
  container_id?: number;
  page?: string;
}

export interface Container {
  id: number;
  shipment_id: number;
  container_number?: string | null;
  container_type?: string | null;
  cbm?: number | null;
  boxes_total?: number | null;
  gross_weight_kg?: number | null;
  container_status?: string | null;
  eta_israel?: string | null;
  eta_port?: string | null;
  eta_warehouse?: string | null;
  actual_arrival_israel?: string | null;
  actual_arrival_port?: string | null;
  actual_arrival_warehouse?: string | null;
  warehouse_readiness_status?: string | null;
  unloading_priority?: string | null;
  extra_work_required?: boolean | null;
  extra_work_note?: string | null;
  notes?: string | null;
  shipment_shp_id?: string | null;
  supplier?: string | null;
  goods_description?: string | null;
  effective_eta_israel?: string | null;
  effective_eta_warehouse?: string | null;
  updated_at?: string | null;

  // Categories
  category?: string | null;
  effective_category?: string | null;

  // Receiving (warehouse)
  received_cartons_actual?: number | null;
  received_pallets_actual?: number | null;
  received_notes?: string | null;
  received_by?: string | null;
  received_at?: string | null;
  receiving_status?: "not_received" | "partially_received" | "received" | "discrepancy" | string | null;

  // Carton dimensions
  carton_length_cm?: number | null;
  carton_width_cm?: number | null;
  carton_height_cm?: number | null;

  // Pallet calc results
  pallet_type_preference?: "auto" | "euro" | "industrial" | string | null;
  estimated_pallets_euro?: number | null;
  estimated_pallets_industrial?: number | null;
  recommended_pallet_type?: string | null;
  estimated_pallets_final?: number | null;
  pallet_calc_notes?: string | null;

  /** Per-field manual-override metadata. Same shape as Shipment.manual_overrides. */
  manual_overrides?: Record<string, { by?: string; at?: string }> | null;
}

export interface PalletPackingDetail {
  pallet_type: string;
  pallet_length_cm: number;
  pallet_width_cm: number;
  pallet_height_cm: number;
  available_carton_height_cm: number;
  cartons_per_layer: number;
  layers: number;
  cartons_per_pallet: number;
  cartons_stack_height_cm: number | null;
  total_loaded_height_cm: number | null;
  pallets_needed: number | null;
  note?: string | null;
}

export interface PalletBreakdown {
  container_id: number;
  container_number?: string | null;
  method: "dimensions" | "cbm_fallback" | "insufficient_data";
  cartons_total?: number | null;
  carton_length_cm?: number | null;
  carton_width_cm?: number | null;
  carton_height_cm?: number | null;
  pallet_height_cm?: number;
  max_total_height_cm?: number;
  available_carton_height_cm?: number;
  euro: PalletPackingDetail | null;
  industrial: PalletPackingDetail | null;
  recommended_pallet_type: string | null;
  estimated_pallets_final: number | null;
  notes: string;
}

export interface ExtraWork {
  id: number;
  shipment_id: number;
  container_id?: number | null;
  work_type: string;
  work_description?: string | null;
  responsible_party?: string | null;
  external_supplier_name?: string | null;
  work_status?: string | null;
  expected_start_date?: string | null;
  actual_start_date?: string | null;
  expected_end_date?: string | null;
  actual_end_date?: string | null;
  delay_status?: boolean | null;
  delay_reason?: string | null;
  ready_for_distribution_estimated_date?: string | null;
  ready_for_distribution_actual_date?: string | null;
  branch_entry_eta?: string | null;
  branch_entry_actual_date?: string | null;
  notes?: string | null;
  shp_id?: string | null;
  supplier?: string | null;
  container_number?: string | null;
}

export interface EmailAttachment {
  id: number;
  filename?: string | null;
  file_type?: string | null;
  document_type?: string | null;
}

export interface EmailUpdate {
  id: number;
  email_message_id?: string | null;
  email_thread_id?: string | null;
  sender?: string | null;
  subject?: string | null;
  received_at?: string | null;
  body_excerpt?: string | null;
  full_body_text?: string | null;
  attachment_names?: string[] | null;
  detected_shipment_id?: number | null;
  detected_container_id?: number | null;
  confidence_score?: number | null;
  detected_fields_json?: Record<string, any> | null;
  detection_type?: string | null;
  status: string;
  approved_by?: string | null;
  approved_at?: string | null;
  rejected_by?: string | null;
  rejected_at?: string | null;
  created_at?: string | null;
  auto_applied?: boolean | null;
  needs_review?: boolean | null;
  review_reason?: string | null;
  applied_fields_json?: any | null;
  flagged_fields_json?: any | null;
  detected_shp_id?: string | null;
  attachments: EmailAttachment[];
}

export interface PendingContainer {
  id: number;
  pending_shipment_id: number;
  detected_container_number?: string | null;
  detected_container_type?: string | null;
  detected_cbm?: number | null;
  detected_boxes_total?: number | null;
  detected_gross_weight_kg?: number | null;
  detected_eta_israel?: string | null;
  detected_eta_port?: string | null;
  detected_eta_warehouse?: string | null;
  detected_notes?: string | null;
}

export interface PendingShipment {
  id: number;
  source_email_update_id?: number | null;
  detected_supplier?: string | null;
  detected_goods_description?: string | null;
  detected_origin_country?: string | null;
  detected_origin_port?: string | null;
  detected_shipping_channel?: string | null;
  detected_etd?: string | null;
  detected_eta_israel?: string | null;
  detected_eta_port?: string | null;
  detected_eta_warehouse?: string | null;
  detected_customs_broker?: string | null;
  detected_booking_number?: string | null;
  detected_bol_number?: string | null;
  detected_invoice_number?: string | null;
  detected_po_number?: string | null;
  detected_goods_value_usd?: number | null;
  detected_freight_price_usd?: number | null;
  detected_paperwork_complete?: boolean | null;
  detected_notes?: string | null;
  confidence_score?: number | null;
  status: string;
  rejection_reason?: string | null;
  assigned_shipment_id?: number | null;
  created_at?: string | null;
  sender?: string | null;
  subject?: string | null;
  pending_containers: PendingContainer[];
}

export interface DashboardKpis {
  active_shipments: number;
  total_containers_in_transit: number;
  containers_arriving_this_week_israel: number;
  containers_arriving_next_week_israel: number;
  containers_at_port: number;
  containers_to_warehouse: number;
  delayed_shipments: number;
  awaiting_approval: number;
  paperwork_missing: number;
  pending_new_shipments_from_email: number;
  pending_email_updates: number;
  auto_applied_email_updates_today: number;
  shipments_with_open_extra_work: number;
  extra_work_delayed: number;
  total_cbm_in_transit: number;
  last_email_sync_at?: string | null;
}

export interface PalletKpis {
  pallets_today: number;
  containers_today: number;
  pallets_tomorrow: number;
  containers_tomorrow: number;
  pallets_next_7_days: number;
  containers_next_7_days: number;
  containers_missing_carton_dimensions: number;
  shipments_missing_eta: number;
}

export interface DailyForecastDay {
  date: string;
  weekday: string;
  containers_arriving: number;
  shipment_ids: number[];
  suppliers: string[];
  total_cartons: number;
  total_cbm: number;
  estimated_pallets: number;
  missing_carton_dimensions: number;
  is_today: boolean;
  is_tomorrow: boolean;
}

export interface ForecastWeek {
  week_index: number;
  week_label: string;
  week_start: string;
  week_end: string;
  containers_arriving_israel: number;
  containers_arriving_port: number;
  containers_arriving_warehouse: number;
  cbm_total: number;
  weight_total_kg: number;
  boxes_total: number;
  suppliers: string[];
  load_status: string;
  container_ids: number[];
}

export interface ActionItem {
  type: string;
  title: string;
  count: number;
  severity: string;
  link?: string | null;
}

export interface Alert {
  id: number;
  alert_type: string;
  severity: string;
  shipment_id?: number | null;
  container_id?: number | null;
  extra_work_task_id?: number | null;
  email_update_id?: number | null;
  pending_shipment_id?: number | null;
  title: string;
  description?: string | null;
  due_date?: string | null;
  resolved: boolean;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
  shp_id?: string | null;
}

export interface ShipmentEvent {
  id: number;
  entity_type: string;
  entity_id: number;
  action_type: string;
  field_changed?: string | null;
  old_value?: string | null;
  new_value?: string | null;
  changed_by?: string | null;
  changed_at: string;
  source: string;
  note?: string | null;
}

export interface ListResponse<T> {
  items: T[];
  total: number;
}
