import { api } from './api';
import type {
  KnowledgeHit,
  Message,
  Page,
  ResolveRequest,
  SLA,
  Ticket,
  TicketCreate,
  TicketDetail,
} from '../types';

export interface TicketFilters {
  status?: string;
  category?: string;
  priority?: string;
  mine?: boolean;
  search?: string;
  skip?: number;
  limit?: number;
}

export const ticketService = {
  async list(filters: TicketFilters = {}): Promise<Page<Ticket>> {
    const { data } = await api.get<Page<Ticket>>('/tickets', { params: filters });
    return data;
  },

  async get(id: string): Promise<TicketDetail> {
    const { data } = await api.get<TicketDetail>(`/tickets/${id}`);
    return data;
  },

  async create(body: TicketCreate): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>('/tickets', body);
    return data;
  },

  async addMessage(id: string, body: string, isInternal = false): Promise<Message> {
    const { data } = await api.post<Message>(`/tickets/${id}/messages`, {
      body,
      is_internal: isInternal,
    });
    return data;
  },

  async suggestions(id: string): Promise<KnowledgeHit[]> {
    const { data } = await api.get<KnowledgeHit[]>(`/tickets/${id}/suggestions`);
    return data;
  },

  async sla(id: string): Promise<SLA> {
    const { data } = await api.get<SLA>(`/tickets/${id}/sla`);
    return data;
  },

  async assign(id: string, teamId?: string, assigneeUserId?: string): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>(`/tickets/${id}/assign`, {
      team_id: teamId ?? null,
      assignee_user_id: assigneeUserId ?? null,
    });
    return data;
  },

  async start(id: string): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>(`/tickets/${id}/start`);
    return data;
  },

  async escalate(id: string, reason: string): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>(`/tickets/${id}/escalate`, { reason });
    return data;
  },

  async resolve(id: string, body: ResolveRequest): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>(`/tickets/${id}/resolve`, body);
    return data;
  },

  async close(id: string): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>(`/tickets/${id}/close`);
    return data;
  },

  async reopen(id: string, reason: string): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>(`/tickets/${id}/reopen`, { reason });
    return data;
  },

  async cancel(id: string): Promise<TicketDetail> {
    const { data } = await api.post<TicketDetail>(`/tickets/${id}/cancel`);
    return data;
  },
};
