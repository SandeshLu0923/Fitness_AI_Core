/**
 * API Module
 * Centralized HTTP client configuration and standardized response handling
 */

export { default as apiClient, get, post, put, del } from "./apiClient";
export type { ApiResponse } from "./apiClient";
