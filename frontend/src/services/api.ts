import axios from 'axios';
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { storage, getJTIFromToken } from '../utils/storage';

// Types
interface LoginUrlResponse {
  authorization_url: string;
}

interface OAuthCallbackRequest {
  code: string;
  state: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  username: string;
}

interface RefreshRequest {
  refresh_token: string;
  jti: string;
}

interface MeResponse {
  username: string;
  message: string;
}

interface AppLogRequest {
  source_service: string;
  level: string;
  message: string;
  environment: string;
  created_at: string;
  trace_id?: string;
  context_json?: Record<string, any>;
}

interface AppLogResponse {
  log_id: number;
  ingested_at: string;
}

interface AuditLogRequest {
  source_service: string;
  environment: string;
  actor_id: string;
  actor_type: 'USER' | 'SERVICE' | 'SYSTEM';
  action: string;
  target_resource: string;
  outcome: 'SUCCESS' | 'FAILURE' | 'PARTIAL';
  event_time: string;
  ip_address?: string;
  detail_json?: Record<string, any>;
}

interface AuditLogResponse {
  log_id: number;
  ingested_at: string;
}

interface LogEntry {
  log_type: 'app' | 'audit';
  id: number;
  source_service: string;
  level?: string;
  actor_id?: string;
  actor_type?: string;
  action?: string;
  outcome?: string;
  message?: string;
  environment: string;
  created_at?: string;
  event_time?: string;
  ingested_at: string;
  [key: string]: any;
}

interface PaginatedLogsResponse {
  data: LogEntry[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

interface HealthResponse {
  status: string;
  database: {
    status: string;
    latency_ms?: number;
    detail?: string;
  };
  cache: {
    status: string;
    latency_ms?: number;
    detail?: string;
  };
  version: string;
  uptime_seconds: number;
}

interface MetricsResponse {
  ingestion_total: number;
  query_total: number;
  cache_hit_ratio: number;
  cache_hits: number;
  cache_misses: number;
  error_total?: Record<string, number>;
  retention_last_run?: string;
  retention_deleted_count?: number;
}

interface ErrorResponse {
  error_code: string;
  message: string;
  details?: Record<string, any>;
  request_id: string;
}

const VITE_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://lms-api.voicollo.com/api/v1';

// Create axios instance
let apiClient: AxiosInstance;

// Flag to prevent token refresh loops
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

const onRefreshed = (token: string) => {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
};

const addRefreshSubscriber = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback);
};

// Initialize API client
export const initializeApiClient = () => {
  apiClient = axios.create({
    baseURL: VITE_API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor to add auth token
  apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = storage.getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor to handle token refresh
  apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

      if (error.response?.status === 401 && !originalRequest._retry) {
        if (isRefreshing) {
          // Wait for refresh to complete
          return new Promise((resolve) => {
            addRefreshSubscriber((token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(apiClient(originalRequest));
            });
          });
        }

        isRefreshing = true;
        originalRequest._retry = true;

        try {
          const refreshToken = storage.getRefreshToken();
          const jti = storage.getJTI();

          if (refreshToken && jti) {
            const response = await apiClient.post<TokenResponse>('/auth/refresh', {
              refresh_token: refreshToken,
              jti,
            });

            const { access_token, refresh_token: newRefreshToken, username } = response.data;
            const newJTI = getJTIFromToken(access_token);

            storage.setAccessToken(access_token);
            storage.setRefreshToken(newRefreshToken);
            storage.setUsername(username);
            if (newJTI) {
              storage.setJTI(newJTI);
            }

            apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
            originalRequest.headers.Authorization = `Bearer ${access_token}`;

            isRefreshing = false;
            onRefreshed(access_token);

            return apiClient(originalRequest);
          }
        } catch (refreshError) {
          isRefreshing = false;
          storage.clearAll();
          window.location.href = '/';
          return Promise.reject(refreshError);
        }
      }

      return Promise.reject(error);
    }
  );

  return apiClient;
};

// API Methods
export const authAPI = {
  getLoginUrl: async (): Promise<string> => {
    const response = await apiClient.get<LoginUrlResponse>('/auth/login');
    return response.data.authorization_url;
  },

  callback: async (code: string, state: string): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/callback', {
      code,
      state,
    });
    return response.data;
  },

  me: async (): Promise<MeResponse> => {
    const response = await apiClient.get<MeResponse>('/auth/me');
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
    storage.clearAll();
  },
};

export const logsAPI = {
  queryLogs: async (params: {
    log_type?: 'app' | 'audit' | 'both';
    level?: string;
    source_service?: string;
    start_time?: string;
    end_time?: string;
    actor_id?: string;
    trace_id?: string;
    sort?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }): Promise<PaginatedLogsResponse> => {
    const response = await apiClient.get<PaginatedLogsResponse>('/logs', { params });
    return response.data;
  },

  getLog: async (logType: 'app' | 'audit', logId: number): Promise<LogEntry> => {
    const response = await apiClient.get<LogEntry>(`/logs/${logType}/${logId}`);
    return response.data;
  },

  ingestAppLog: async (log: AppLogRequest): Promise<AppLogResponse> => {
    const response = await apiClient.post<AppLogResponse>('/logs/app', log);
    return response.data;
  },

  ingestAuditLog: async (log: AuditLogRequest): Promise<AuditLogResponse> => {
    const response = await apiClient.post<AuditLogResponse>('/logs/audit', log);
    return response.data;
  },

  exportLogs: async (params: {
    log_type?: 'app' | 'audit' | 'both';
    level?: string;
    source_service?: string;
    start_time?: string;
    end_time?: string;
    actor_id?: string;
    trace_id?: string;
    sort?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
    format?: 'json' | 'csv';
  }): Promise<Blob> => {
    const response = await apiClient.get('/logs/export', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },
};

export const adminAPI = {
  health: async (): Promise<HealthResponse> => {
    const response = await apiClient.get<HealthResponse>('/health');
    return response.data;
  },

  metrics: async (): Promise<MetricsResponse> => {
    const response = await apiClient.get<MetricsResponse>('/metrics');
    return response.data;
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// ADD THESE TYPES + servicesAPI object to your existing api.ts
// ─────────────────────────────────────────────────────────────────────────────

// Types -----------------------------------------------------------------------
 
export interface ServiceEntry {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at?: string;
}
 
export interface AddServiceRequest {
  id: string;
  name: string;
  description?: string;
}
 
export interface AddServiceResponse {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at?: string;
}
 
export interface ServiceQueryResponse {
  services: ServiceEntry[];
}
 
export interface DisableServiceResponse {
  id: string;
  is_active: false;
}
 
export interface EnableServiceResponse {
  id: string;
  is_active: true;
}
 
// API object ------------------------------------------------------------------
 
export const servicesAPI = {
  /** POST /services */
  registerService: async (body: AddServiceRequest): Promise<AddServiceResponse> => {
    const response = await apiClient.post('/services', body);
    return response.data;
  },
 
  /** GET /services?name=&id= */
  queryServices: async (params?: { name?: string; id?: string }): Promise<ServiceQueryResponse> => {
    const response = await apiClient.get('/services', { params });
    return response.data;
  },
 
  /** GET /services/{service_id} */
  getService: async (serviceId: string): Promise<ServiceEntry> => {
    const response = await apiClient.get(`/services/${serviceId}`);
    return response.data;
  },
 
  /** PATCH /services/{service_id}/disable */
  disableService: async (serviceId: string): Promise<DisableServiceResponse> => {
    const response = await apiClient.patch(`/services/${serviceId}/disable`);
    return response.data;
  },
 
  /** PATCH /services/{service_id}/enable */
  enableService: async (serviceId: string): Promise<EnableServiceResponse> => {
    const response = await apiClient.patch(`/services/${serviceId}/enable`);
    return response.data;
  },
};

// Export types
export type {
  LoginUrlResponse,
  OAuthCallbackRequest,
  TokenResponse,
  RefreshRequest,
  MeResponse,
  AppLogRequest,
  AppLogResponse,
  AuditLogRequest,
  AuditLogResponse,
  LogEntry,
  PaginatedLogsResponse,
  HealthResponse,
  MetricsResponse,
  ErrorResponse,
};
