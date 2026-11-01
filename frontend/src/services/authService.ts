import { api, TOKEN_KEY } from './api';
import type { TokenResponse, User } from '../types';

export const authService = {
  async login(username: string, password: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>('/auth/login', { username, password });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    return data;
  },

  async logout(): Promise<void> {
    try {
      await api.post('/auth/logout');
    } finally {
      localStorage.removeItem(TOKEN_KEY);
    }
  },

  async me(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
    return data;
  },

  hasToken(): boolean {
    return localStorage.getItem(TOKEN_KEY) !== null;
  },
};
