import { api } from './api';
import type {
  AdminUser,
  AuditLogEntry,
  EvaluationMetrics,
  OverviewMetrics,
  Page,
  PerformanceMetrics,
  SLA,
  SLAMetrics,
  TicketMetrics,
} from '../types';

export const analyticsService = {
  async overview(): Promise<OverviewMetrics> {
    return (await api.get<OverviewMetrics>('/analytics/overview')).data;
  },
  async mySummary(): Promise<OverviewMetrics> {
    return (await api.get<OverviewMetrics>('/analytics/my-summary')).data;
  },
  async tickets(): Promise<TicketMetrics> {
    return (await api.get<TicketMetrics>('/analytics/tickets')).data;
  },
  async performance(): Promise<PerformanceMetrics> {
    return (await api.get<PerformanceMetrics>('/analytics/performance')).data;
  },
  async evaluation(): Promise<EvaluationMetrics> {
    return (await api.get<EvaluationMetrics>('/analytics/evaluation')).data;
  },
  async slaMetrics(): Promise<SLAMetrics> {
    return (await api.get<SLAMetrics>('/sla/metrics')).data;
  },
  async slaList(params: { status?: string; breached?: boolean } = {}): Promise<Page<SLA>> {
    return (await api.get<Page<SLA>>('/sla', { params: { ...params, limit: 100 } })).data;
  },
  async users(): Promise<Page<AdminUser>> {
    return (await api.get<Page<AdminUser>>('/admin/users', { params: { limit: 200 } })).data;
  },
  async updateUser(
    id: string,
    body: { is_active?: boolean; can_view_sensitive?: boolean; roles?: string[] },
  ): Promise<AdminUser> {
    return (await api.patch<AdminUser>(`/admin/users/${id}`, body)).data;
  },
  async auditLogs(params: { event_type?: string; entity_type?: string } = {}): Promise<Page<AuditLogEntry>> {
    return (await api.get<Page<AuditLogEntry>>('/admin/audit-logs', { params: { ...params, limit: 100 } })).data;
  },
};
