import apiClient from './client';
import type { SnapshotCreate, SnapshotResponse, SnapshotUpdate } from '../types';

export async function createSnapshot(payload: SnapshotCreate): Promise<SnapshotResponse> {
  const { data } = await apiClient.post<SnapshotResponse>('/snapshots/', payload);
  return data;
}

export async function listSnapshots(): Promise<SnapshotResponse[]> {
  const { data } = await apiClient.get<SnapshotResponse[]>('/snapshots/');
  return data;
}

export async function getSnapshot(id: string): Promise<SnapshotResponse> {
  const { data } = await apiClient.get<SnapshotResponse>(`/snapshots/${id}`);
  return data;
}

export async function updateSnapshot(id: string, payload: SnapshotUpdate): Promise<SnapshotResponse> {
  const { data } = await apiClient.put<SnapshotResponse>(`/snapshots/${id}`, payload);
  return data;
}

export async function deleteSnapshot(id: string): Promise<void> {
  await apiClient.delete(`/snapshots/${id}`);
}
