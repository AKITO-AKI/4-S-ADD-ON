import apiClient from './client';
import type { LoraModelListResponse, LoraUploadResponse } from '../types';

export async function listLoraModels(userId: string): Promise<LoraModelListResponse> {
  const { data } = await apiClient.get<LoraModelListResponse>(`/models/${userId}/lora`);
  return data;
}

export async function uploadLoraModel(userId: string, file: File): Promise<LoraUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<LoraUploadResponse>(`/models/${userId}/lora`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteLoraModel(userId: string, filename: string): Promise<void> {
  await apiClient.delete(`/models/${userId}/lora/${encodeURIComponent(filename)}`);
}
