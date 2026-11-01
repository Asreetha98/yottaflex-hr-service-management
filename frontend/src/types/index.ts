export type Role = 'EMPLOYEE' | 'MANAGER' | 'HR_PARTNER' | 'IT_OPS' | 'ADMIN';

export type TicketStatus =
  | 'NEW'
  | 'CLASSIFIED'
  | 'AWAITING_CLARIFICATION'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'ESCALATED'
  | 'RESOLVED'
  | 'CLOSED'
  | 'REOPENED'
  | 'CANCELLED';

export type Priority = 'P1' | 'P2' | 'P3';

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface User {
  user_id: string;
  username: string;
  email: string;
  employee_id: string | null;
  is_active: boolean;
  can_view_sensitive: boolean;
  roles: string[];
  permissions: string[];
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Message {
  message_id: string;
  ticket_id: string;
  sequence_number: number;
  sender_user_id: string | null;
  sender_type: string;
  message_type: string;
  is_internal: boolean;
  body: string;
  created_at: string;
}

export interface TicketEvent {
  event_id: string;
  ticket_id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  actor_user_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface Assignment {
  assignment_id: string;
  ticket_id: string;
  team_id: string;
  assigned_user_id: string | null;
  assignment_type: string;
  routing_reason: string;
  rule_reference: string | null;
  is_current: boolean;
  assigned_at: string;
}

export interface Escalation {
  escalation_id: string;
  ticket_id: string;
  from_team_id: string | null;
  to_team_id: string | null;
  escalation_level: string;
  reason_code: string;
  reason: string;
  escalated_at: string;
  status: string;
}

export interface Resolution {
  resolution_id: string;
  ticket_id: string;
  resolution_type: string;
  summary: string;
  resolution_text: string;
  policy_version_id: string | null;
  citation_id: string | null;
  article_id: string | null;
  resolved_by: string;
  resolved_at: string;
  satisfaction_score: number | null;
  was_reopened: boolean;
}

export interface Ticket {
  ticket_id: string;
  requester_id: string;
  subject: string;
  description: string;
  category_code: string | null;
  priority: Priority;
  status: TicketStatus;
  channel: string;
  is_sensitive: boolean;
  access_level: string;
  sensitive_patterns: string[] | null;
  classification_confidence: number | null;
  classification_explanation: Record<string, unknown> | null;
  is_ambiguous: boolean;
  assigned_team_id: string | null;
  assigned_user_id: string | null;
  reopen_count: number;
  first_response_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketDetail extends Ticket {
  messages: Message[];
  events: TicketEvent[];
  assignments: Assignment[];
  escalations: Escalation[];
  resolutions: Resolution[];
}

export interface TicketCreate {
  subject: string;
  description: string;
  channel?: string;
}

export interface ResolveRequest {
  resolution_type: string;
  summary: string;
  resolution_text: string;
  policy_version_id?: string | null;
}

export interface Citation {
  policy_id: string;
  policy_title: string;
  version_id: string;
  version_number: number;
  section_reference: string | null;
  excerpt: string | null;
}

export interface KnowledgeHit {
  article_id: string;
  title: string;
  answer_snippet: string;
  confidence: number;
  policy_version_id: string | null;
  policy_backed: boolean;
  citation: Citation | null;
  matched_terms: string[];
}

export interface KnowledgeArticle {
  article_id: string;
  title: string;
  summary: string | null;
  content: string;
  category_code: string | null;
  policy_version_id: string | null;
  keywords: string[];
  audience: string[];
  status: string;
  view_count: number;
}

export interface PolicyDocument {
  policy_id: string;
  title: string;
  description: string | null;
  category_id: string | null;
  owner_department_id: string;
  status: string;
  created_at: string;
}

export interface PolicyVersion {
  version_id: string;
  policy_id: string;
  version_number: number;
  title: string;
  content: string;
  summary: string | null;
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
  effective_from: string | null;
  effective_to: string | null;
  published_at: string | null;
  supersedes_version_id: string | null;
  created_at: string;
}

export interface PolicyValidity {
  policy_id: string;
  reference_date: string;
  version_id: string | null;
  exception_code: string | null;
  exception_message: string | null;
  latest_created: string | null;
  latest_published: string | null;
  currently_effective: string | null;
  historically_effective: string | null;
  overlap_detected: boolean;
  explanation: string;
}

export interface SLA {
  sla_id: string;
  ticket_id: string;
  sla_policy: string;
  priority: Priority;
  target_hours: number;
  started_at: string;
  due_at: string;
  resolved_at: string | null;
  total_paused_business_minutes: number;
  status: 'ACTIVE' | 'PAUSED' | 'MET' | 'BREACHED';
  is_breached: boolean;
}

export interface SLAMetrics {
  total: number;
  active: number;
  paused: number;
  met: number;
  breached: number;
  warning: number;
  compliance_rate: number | null;
  by_policy: Record<string, { total: number; met: number; breached: number }>;
}

export interface OverviewMetrics {
  total_tickets: number;
  open_tickets: number;
  resolved_tickets: number;
  awaiting_clarification: number;
  escalated_tickets: number;
  sensitive_tickets: number;
  created_last_24h: number;
  sla_compliance_rate: number | null;
  sla_breached: number;
  sla_warning: number;
}

export interface TicketMetrics {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_category: Record<string, number>;
  by_channel: Record<string, number>;
  daily_volume: { date: string; count: number }[];
  ambiguous: number;
}

export interface PerformanceMetrics {
  avg_resolution_business_hours: number | null;
  avg_first_response_business_hours: number | null;
  sla_compliance_rate: number | null;
  reopen_rate: number | null;
  escalation_rate: number | null;
  avg_satisfaction: number | null;
  resolved_count: number;
}

export interface EvaluationMetrics {
  available: boolean;
  reason: string | null;
  evaluated: number;
  category_accuracy: number | null;
  sensitive_precision: number | null;
  sensitive_recall: number | null;
}

export interface AdminUser {
  user_id: string;
  username: string;
  email: string;
  employee_id: string | null;
  is_active: boolean;
  can_view_sensitive: boolean;
  roles: string[];
  last_login_at: string | null;
}

export interface AuditLogEntry {
  event_id: string;
  event_type: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  actor_user_id: string | null;
  actor_role: string | null;
  created_at: string;
}

export interface ApiError {
  detail: string;
  code?: string;
}
