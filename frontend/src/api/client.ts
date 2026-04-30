import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
});

/** Attach the stored JWT token to every outgoing request. */
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;
