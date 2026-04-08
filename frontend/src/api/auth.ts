import request from '@/utils/request'
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
  PasswordChangeRequest,
} from '@/types'

// Authentication API
export const authApi = {
  // Login
  login(data: LoginRequest): Promise<TokenResponse> {
    return request.post('/auth/login', data)
  },

  // Register
  register(data: RegisterRequest): Promise<TokenResponse> {
    return request.post('/auth/register', data)
  },

  // Logout
  logout(): Promise<void> {
    return request.post('/auth/logout')
  },

  // Refresh token
  refreshToken(refreshToken: string): Promise<TokenResponse> {
    return request.post('/auth/refresh', { refresh_token: refreshToken })
  },

  // Get current user profile
  getCurrentUser(): Promise<User> {
    return request.get('/auth/me')
  },

  // Change password
  changePassword(data: PasswordChangeRequest): Promise<void> {
    return request.post('/auth/change-password', data)
  },
}
