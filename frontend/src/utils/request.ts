import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

// Create axios instance
const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add JWT token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors
request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    const { response } = error

    if (response) {
      switch (response.status) {
        case 401:
          // Token expired or invalid
          ElMessage.error('Authentication failed. Please login again.')
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          router.push('/login')
          break

        case 403:
          ElMessage.error('You do not have permission to perform this action.')
          break

        case 404:
          ElMessage.error('Resource not found.')
          break

        case 500:
          ElMessage.error('Server error. Please try again later.')
          break

        default:
          ElMessage.error(response.data?.detail || 'An error occurred.')
      }
    } else {
      ElMessage.error('Network error. Please check your connection.')
    }

    return Promise.reject(error)
  }
)

export default request
