// Environment configuration
// This file can be used to configure the API base URL and other settings

const VITE_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://lms-api.voicollo.com/api/v1';

export const config = {
  apiBaseUrl: VITE_API_BASE_URL,
};
