import request from '@/utils/request'
import type {
  AuthSession,
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
  logout(refreshToken?: string): Promise<void> {
    return request.post('/auth/logout', {
      refresh_token: refreshToken ?? null,
    })
  },

  // Refresh token
  refreshToken(refreshToken: string): Promise<TokenResponse> {
    return request.post('/auth/refresh', { refresh_token: refreshToken })
  },

  // List current user's active sessions
  getMySessions(): Promise<AuthSession[]> {
    return request.get('/auth/sessions/me')
  },

  // Revoke one of the current user's active sessions
  revokeMySession(sessionId: string): Promise<{ message: string }> {
    return request.delete(`/auth/sessions/me/${sessionId}`)
  },

  // List active sessions for administration
  getSessions(authUserId?: number, username?: string): Promise<AuthSession[]> {
    const params: any = {}
    if (authUserId !== undefined) {
      params.auth_user_id = authUserId
    }
    if (username) {
      params.username = username
    }
    return request.get('/auth/sessions', {
      params: Object.keys(params).length > 0 ? params : undefined,
    })
  },

  // Revoke an active session by session id
  revokeSession(sessionId: string): Promise<{ message: string }> {
    return request.delete(`/auth/sessions/${sessionId}`)
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
