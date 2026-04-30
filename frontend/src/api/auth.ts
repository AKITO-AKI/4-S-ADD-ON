import apiClient from './client';
import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse } from '../types';

export async function register(payload: RegisterRequest): Promise<UserResponse> {
  const { data } = await apiClient.post<UserResponse>('/auth/register', payload);
  return data;
}

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', payload);
  return data;
}
