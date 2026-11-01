import { api } from './api';
import type {
  KnowledgeArticle,
  KnowledgeHit,
  Page,
  PolicyDocument,
  PolicyValidity,
  PolicyVersion,
} from '../types';

export const policyService = {
  async list(): Promise<Page<PolicyDocument>> {
    const { data } = await api.get<Page<PolicyDocument>>('/policies', { params: { limit: 200 } });
    return data;
  },

  async create(title: string, ownerDepartmentId: string, description?: string): Promise<PolicyDocument> {
    const { data } = await api.post<PolicyDocument>('/policies', {
      title,
      owner_department_id: ownerDepartmentId,
      description: description || null,
    });
    return data;
  },

  async versions(policyId: string): Promise<PolicyVersion[]> {
    const { data } = await api.get<PolicyVersion[]>(`/policies/${policyId}/versions`);
    return data;
  },

  async createVersion(
    policyId: string,
    body: { title: string; content: string; summary?: string; effective_from?: string },
  ): Promise<PolicyVersion> {
    const { data } = await api.post<PolicyVersion>(`/policies/${policyId}/versions`, body);
    return data;
  },

  async publish(versionId: string, effectiveFrom?: string): Promise<PolicyVersion> {
    const { data } = await api.post<PolicyVersion>(`/policies/versions/${versionId}/publish`, {
      effective_from: effectiveFrom ?? null,
    });
    return data;
  },

  async archive(versionId: string): Promise<PolicyVersion> {
    const { data } = await api.post<PolicyVersion>(`/policies/versions/${versionId}/archive`);
    return data;
  },

  async effective(policyId: string, referenceDate?: string): Promise<PolicyValidity> {
    const { data } = await api.get<PolicyValidity>(`/policies/${policyId}/effective`, {
      params: { reference_date: referenceDate },
    });
    return data;
  },

  async searchKnowledge(query: string, category?: string): Promise<KnowledgeHit[]> {
    const { data } = await api.post<KnowledgeHit[]>('/knowledge/search', {
      query,
      category: category || null,
      limit: 10,
    });
    return data;
  },

  async articles(category?: string): Promise<Page<KnowledgeArticle>> {
    const { data } = await api.get<Page<KnowledgeArticle>>('/knowledge/articles', {
      params: { category, limit: 100 },
    });
    return data;
  },

  async article(id: string): Promise<KnowledgeArticle> {
    const { data } = await api.get<KnowledgeArticle>(`/knowledge/articles/${id}`);
    return data;
  },
};
