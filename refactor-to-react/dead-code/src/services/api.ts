import axios from 'axios';

// Create Axios instance with base URL (env var or default to localhost:8000 for dev)
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Here we can dispatch a global toast event or handle unauthorized access
    if (error.response) {
      console.error('API Error:', error.response.data);
      if (error.response.status === 401) {
        // Handle unauthorized (e.g., redirect to auth)
      }
    } else {
      console.error('Network Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
