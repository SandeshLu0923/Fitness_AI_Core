/**
 * Centralized API Client
 * Standardizes HTTP communication, error handling, and response format.
 * All API responses follow: { status: "success" | "error", message?: string, data?: any }
 */

import axios, { type AxiosInstance, AxiosError, type AxiosResponse } from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function rewriteLocalBackendUrl(url?: string): string | undefined {
  if (!url) return url;
  return url.replace(/^http:\/\/localhost:8000/, API_BASE_URL).replace(/^http:\/\/127\.0\.0\.1:8000/, API_BASE_URL);
}

axios.interceptors.request.use((config) => {
  if ((config as any).skipApiRewrite) return config;
  config.url = rewriteLocalBackendUrl(config.url);
  return config;
});

// API Response Type - consistent across all endpoints
export interface ApiResponse<T = any> {
  status: "success" | "error";
  message?: string;
  data?: T;
}

// Create Axios instance with base configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for adding auth tokens (if needed in future)
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token to headers if available
    const token = sessionStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for standardized error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    return response as any;
  },
  (error: AxiosError<ApiResponse>) => {
    // Extract error message from backend response
    const errorMessage =
      error.response?.data?.message ||
      error.message ||
      "An unexpected error occurred";

    const apiError: ApiResponse = {
      status: "error",
      message: errorMessage,
    };

    return Promise.reject(apiError);
  }
);

/**
 * Generic GET request wrapper
 */
export async function get<T>(url: string): Promise<ApiResponse<T>> {
  return apiClient.get<ApiResponse<T>>(url).then((res) => res as any);
}

/**
 * Generic POST request wrapper
 */
export async function post<T>(
  url: string,
  data: any
): Promise<ApiResponse<T>> {
  return apiClient
    .post<ApiResponse<T>>(url, data)
    .then((res) => res as any);
}

/**
 * Generic PUT request wrapper
 */
export async function put<T>(
  url: string,
  data: any
): Promise<ApiResponse<T>> {
  return apiClient.put<ApiResponse<T>>(url, data).then((res) => res as any);
}

/**
 * Generic DELETE request wrapper
 */
export async function del<T>(url: string): Promise<ApiResponse<T>> {
  return apiClient.delete<ApiResponse<T>>(url).then((res) => res as any);
}

export default apiClient;
