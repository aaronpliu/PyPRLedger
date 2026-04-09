# Phase 2: Vue 3 Frontend Refactoring Implementation Plan

## 📋 Overview

Phase 2 focuses on refactoring the frontend from static HTML to a modern Vue 3 application with TypeScript, providing better maintainability, component reusability, and enhanced user experience.

**Implementation Period**: Days 1-10  
**Target Completion**: Modern SPA with authentication, RBAC integration, and all existing features

---

## 🎯 Objectives

1. **Modern Tech Stack**: Migrate from static HTML to Vue 3 + Vite + TypeScript
2. **Component Architecture**: Reusable components following Vue best practices
3. **Authentication Integration**: JWT-based auth with token management
4. **RBAC UI Integration**: Role-based UI rendering and route guards
5. **State Management**: Pinia for global state management
6. **Routing**: Vue Router with protected routes
7. **UI Framework**: Element Plus or Ant Design Vue for consistent design
8. **API Integration**: Axios with interceptors for auth and error handling
9. **Internationalization**: Maintain existing i18n support (en, zh-CN, zh-TW)
10. **Performance**: Code splitting, lazy loading, and optimization

---

## 🏗️ Technology Stack

### Core Technologies
- **Framework**: Vue 3.4+ (Composition API)
- **Build Tool**: Vite 5.x
- **Language**: TypeScript 5.x
- **State Management**: Pinia 2.x
- **Routing**: Vue Router 4.x
- **HTTP Client**: Axios 1.x
- **UI Framework**: Element Plus 2.x (recommended) or Ant Design Vue 4.x
- **CSS Preprocessor**: SCSS or Less

### Additional Libraries
- **i18n**: vue-i18n 9.x
- **Icons**: @element-plus/icons-vue or @ant-design/icons-vue
- **Date Handling**: dayjs
- **Charts**: ECharts 5.x (for audit statistics)
- **Code Diff**: diff2html (existing, integrate with Vue)
- **Testing**: Vitest + Vue Test Utils
- **Linting**: ESLint + Prettier

---

## 📁 Project Structure

```
web/
├── public/                  # Static assets
│   ├── favicon.ico
│   └── lib/                # Existing libraries (diff2html)
├── src/
│   ├── api/                # API service layer
│   │   ├── auth.ts
│   │   ├── rbac.ts
│   │   ├── audit.ts
│   │   ├── reviews.ts
│   │   ├── scores.ts
│   │   ├── projects.ts
│   │   └── users.ts
│   ├── assets/             # Assets (images, fonts)
│   │   ├── images/
│   │   └── styles/
│   │       ├── variables.scss
│   │       ├── mixins.scss
│   │       └── global.scss
│   ├── components/         # Reusable components
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppSidebar.vue
│   │   │   ├── AppFooter.vue
│   │   │   ├── LoadingSpinner.vue
│   │   │   └── ErrorBoundary.vue
│   │   ├── auth/
│   │   │   ├── LoginForm.vue
│   │   │   ├── RegisterForm.vue
│   │   │   └── PasswordChange.vue
│   │   ├── reviews/
│   │   │   ├── ReviewCard.vue
│   │   │   ├── ReviewList.vue
│   │   │   ├── ReviewDetail.vue
│   │   │   ├── ReviewForm.vue
│   │   │   └── DiffViewer.vue
│   │   ├── scores/
│   │   │   ├── ScoreDisplay.vue
│   │   │   ├── ScoreForm.vue
│   │   │   └── ScoreChart.vue
│   │   ├── rbac/
│   │   │   ├── RoleSelector.vue
│   │   │   ├── PermissionMatrix.vue
│   │   │   └── UserRoles.vue
│   │   └── audit/
│   │       ├── AuditLogTable.vue
│   │       ├── AuditStats.vue
│   │       └── AuditExport.vue
│   ├── composables/        # Composition API functions
│   │   ├── useAuth.ts
│   │   ├── usePermission.ts
│   │   ├── useReviews.ts
│   │   ├── useScores.ts
│   │   └── useAudit.ts
│   ├── layouts/            # Layout components
│   │   ├── DefaultLayout.vue
│   │   ├── AuthLayout.vue
│   │   └── AdminLayout.vue
│   ├── locales/            # i18n translations
│   │   ├── en.json
│   │   ├── zh-CN.json
│   │   └── zh-TW.json
│   ├── router/             # Vue Router configuration
│   │   ├── index.ts
│   │   └── guards.ts       # Route guards
│   ├── stores/             # Pinia stores
│   │   ├── auth.ts
│   │   ├── app.ts
│   │   ├── reviews.ts
│   │   └── audit.ts
│   ├── types/              # TypeScript type definitions
│   │   ├── auth.ts
│   │   ├── rbac.ts
│   │   ├── review.ts
│   │   ├── score.ts
│   │   └── api.ts
│   ├── utils/              # Utility functions
│   │   ├── request.ts      # Axios instance
│   │   ├── validators.ts
│   │   ├── formatters.ts
│   │   └── storage.ts      # LocalStorage helpers
│   ├── views/              # Page components
│   │   ├── auth/
│   │   │   ├── LoginView.vue
│   │   │   ├── RegisterView.vue
│   │   │   └── ProfileView.vue
│   │   ├── dashboard/
│   │   │   ├── DashboardView.vue
│   │   │   └── StatsView.vue
│   │   ├── reviews/
│   │   │   ├── ReviewListView.vue
│   │   │   ├── ReviewDetailView.vue
│   │   │   └── CreateReviewView.vue
│   │   ├── scores/
│   │   │   ├── ScoreListView.vue
│   │   │   └── ScoreAnalyticsView.vue
│   │   ├── admin/
│   │   │   ├── UserManagementView.vue
│   │   │   ├── RoleManagementView.vue
│   │   │   ├── AuditLogView.vue
│   │   │   └── SystemSettingsView.vue
│   │   └── errors/
│   │       ├── NotFoundView.vue
│   │       └── ForbiddenView.vue
│   ├── App.vue             # Root component
│   └── main.ts             # Application entry point
├── index.html              # HTML template
├── vite.config.ts          # Vite configuration
├── tsconfig.json           # TypeScript configuration
├── package.json            # Dependencies
├── .eslintrc.js            # ESLint configuration
├── .prettierrc             # Prettier configuration
└── README.md               # Frontend documentation
```

---

## 📅 Implementation Schedule

### Day 1-2: Project Setup & Configuration

#### Tasks:
1. **Initialize Vue 3 Project**
   ```bash
   cd web
   npm create vite@latest . -- --template vue-ts
   ```

2. **Install Dependencies**
   ```bash
   npm install vue-router pinia axios element-plus @element-plus/icons-vue
   npm install vue-i18n dayjs echarts diff2html
   npm install -D @types/node sass
   ```

3. **Configure Vite**
   - Proxy configuration for API calls
   - Alias setup (@ -> src/)
   - Build optimization

4. **Setup TypeScript**
   - Strict mode enabled
   - Path aliases
   - Type definitions for API responses

5. **Configure ESLint & Prettier**
   - Vue 3 rules
   - TypeScript rules
   - Auto-fix on save

#### Deliverables:
- ✅ Working Vue 3 + Vite + TypeScript setup
- ✅ Development server running
- ✅ Basic project structure created

---

### Day 3-4: Core Infrastructure

#### Tasks:

1. **API Service Layer** (`src/api/`)
   ```typescript
   // src/utils/request.ts
   import axios from 'axios'
   
   const request = axios.create({
     baseURL: '/api/v1',
     timeout: 30000,
   })
   
   // Request interceptor - add JWT token
   request.interceptors.request.use((config) => {
     const token = localStorage.getItem('access_token')
     if (token) {
       config.headers.Authorization = `Bearer ${token}`
     }
     return config
   })
   
   // Response interceptor - handle errors
   request.interceptors.response.use(
     (response) => response.data,
     (error) => {
       if (error.response?.status === 401) {
         // Token expired, redirect to login
         router.push('/login')
       }
       return Promise.reject(error)
     }
   )
   ```

2. **Type Definitions** (`src/types/`)
   ```typescript
   // src/types/auth.ts
   export interface User {
     id: number
     username: string
     email: string
     is_active: boolean
     last_login_at: string | null
     created_at: string
   }
   
   export interface TokenResponse {
     access_token: string
     refresh_token: string
     token_type: string
     expires_in: number
   }
   ```

3. **Pinia Stores** (`src/stores/`)
   ```typescript
   // src/stores/auth.ts
   import { defineStore } from 'pinia'
   import { ref, computed } from 'vue'
   import { login, logout, refreshToken } from '@/api/auth'
   
   export const useAuthStore = defineStore('auth', () => {
     const user = ref<User | null>(null)
     const accessToken = ref<string>('')
     const refreshTokenValue = ref<string>('')
     
     const isAuthenticated = computed(() => !!accessToken.value)
     
     async function loginAction(credentials: LoginRequest) {
       const response = await login(credentials)
       accessToken.value = response.access_token
       refreshTokenValue.value = response.refresh_token
       await fetchUserProfile()
     }
     
     async function logoutAction() {
       await logout()
       clearAuth()
     }
     
     return {
       user,
       isAuthenticated,
       login: loginAction,
       logout: logoutAction,
     }
   })
   ```

4. **Vue Router Setup** (`src/router/`)
   ```typescript
   // src/router/index.ts
   import { createRouter, createWebHistory } from 'vue-router'
   import { useAuthStore } from '@/stores/auth'
   
   const router = createRouter({
     history: createWebHistory(),
     routes: [
       {
         path: '/login',
         name: 'Login',
         component: () => import('@/views/auth/LoginView.vue'),
         meta: { requiresAuth: false },
       },
       {
         path: '/',
         component: DefaultLayout,
         children: [
           {
             path: '',
             name: 'Dashboard',
             component: () => import('@/views/dashboard/DashboardView.vue'),
             meta: { requiresAuth: true },
           },
         ],
       },
     ],
   })
   
   // Navigation guard
   router.beforeEach((to, from, next) => {
     const authStore = useAuthStore()
     if (to.meta.requiresAuth && !authStore.isAuthenticated) {
       next('/login')
     } else {
       next()
     }
   })
   ```

5. **i18n Configuration** (`src/locales/`)
   - Migrate existing translations from HTML
   - Setup vue-i18n plugin
   - Language switcher component

#### Deliverables:
- ✅ API service layer with interceptors
- ✅ Complete type definitions
- ✅ Auth store with login/logout
- ✅ Router with navigation guards
- ✅ i18n setup with 3 languages

---

### Day 5-6: Authentication UI

#### Tasks:

1. **Login Page** (`src/views/auth/LoginView.vue`)
   - Username/email input
   - Password input with show/hide toggle
   - Remember me checkbox
   - Form validation
   - Error message display
   - Loading states

2. **Register Page** (`src/views/auth/RegisterView.vue`)
   - Username, email, password fields
   - Password strength indicator
   - Confirmation password
   - Validation rules
   - Success/error feedback

3. **Profile Page** (`src/views/auth/ProfileView.vue`)
   - Display user information
   - Change password form
   - Update profile settings
   - View role assignments

4. **Auth Layout** (`src/layouts/AuthLayout.vue`)
   - Centered card layout
   - Background image/gradient
   - Logo and branding
   - Language switcher

5. **Composables** (`src/composables/useAuth.ts`)
   ```typescript
   export function useAuth() {
     const authStore = useAuthStore()
     const router = useRouter()
     
     const handleLogin = async (credentials: LoginRequest) => {
       try {
         await authStore.login(credentials)
         router.push('/')
       } catch (error) {
         // Handle error
       }
     }
     
     return {
       user: computed(() => authStore.user),
       isAuthenticated: computed(() => authStore.isAuthenticated),
       login: handleLogin,
       logout: authStore.logout,
     }
   }
   ```

#### Deliverables:
- ✅ Complete authentication flow
- ✅ Form validation and error handling
- ✅ Protected routes working
- ✅ Token refresh mechanism

---

### Day 7-8: Core Features Migration

#### Tasks:

1. **Dashboard** (`src/views/dashboard/DashboardView.vue`)
   - Statistics cards (total reviews, avg score, etc.)
   - Recent reviews list
   - Quick actions
   - Charts (if applicable)

2. **Review Management**
   - **Review List** (`src/views/reviews/ReviewListView.vue`)
     - Table with sorting/filtering
     - Pagination
     - Search functionality
     - Action buttons (view, edit, delete)
   
   - **Review Detail** (`src/views/reviews/ReviewDetailView.vue`)
     - PR information display
     - Diff viewer integration (diff2html)
     - Comments section
     - Score display
     - Edit/delete actions (with permission check)
   
   - **Create/Edit Review** (`src/views/reviews/CreateReviewView.vue`)
     - Form with validation
     - PR URL input
     - Reviewer selection
     - Submit handler

3. **Score Management**
   - **Score List** (`src/views/scores/ScoreListView.vue`)
     - Filter by project/repository
     - Score distribution chart
     - Export functionality
   
   - **Score Analytics** (`src/views/scores/ScoreAnalyticsView.vue`)
     - Trend charts
     - Comparison views
     - Time range selector

4. **Components Development**
   - Reusable table component
   - Form components
   - Modal dialogs
   - Confirmation dialogs
   - Toast notifications

#### Deliverables:
- ✅ All existing features migrated
- ✅ Component library established
- ✅ Responsive design implemented
- ✅ Permission-based UI rendering

---

### Day 9: RBAC & Admin Features

#### Tasks:

1. **Permission Composable** (`src/composables/usePermission.ts`)
   ```typescript
   export function usePermission() {
     const authStore = useAuthStore()
     
     const hasPermission = (action: string, resourceType: string, resourceId?: string) => {
       // Check user's roles and permissions
       return checkPermission(authStore.user?.id, action, resourceType, resourceId)
     }
     
     const canView = (resourceType: string, resourceId?: string) => 
       hasPermission('read', resourceType, resourceId)
     
     const canEdit = (resourceType: string, resourceId?: string) => 
       hasPermission('update', resourceType, resourceId)
     
     const canDelete = (resourceType: string, resourceId?: string) => 
       hasPermission('delete', resourceType, resourceId)
     
     return {
       hasPermission,
       canView,
       canEdit,
       canDelete,
     }
   }
   ```

2. **User Management** (`src/views/admin/UserManagementView.vue`)
   - User list table
   - Create/edit user
   - Assign roles
   - Activate/deactivate users

3. **Role Management** (`src/views/admin/RoleManagementView.vue`)
   - Role list
   - Create/edit roles
   - Permission matrix editor
   - Assign roles to users

4. **Audit Logs** (`src/views/admin/AuditLogView.vue`)
   - Filterable log table
   - Date range picker
   - Export to CSV/JSON
   - Statistics dashboard
   - Real-time updates (optional)

5. **Route Guards Enhancement**
   - Role-based route access
   - Dynamic menu rendering
   - Hide unauthorized actions

#### Deliverables:
- ✅ RBAC fully integrated in UI
- ✅ Admin panel complete
- ✅ Audit log viewer with filters
- ✅ Permission-based UI elements

---

### Day 10: Polish & Optimization

#### Tasks:

1. **Performance Optimization**
   - Lazy load routes
   - Code splitting
   - Image optimization
   - Bundle analysis

2. **Error Handling**
   - Global error boundary
   - 404 page
   - 403 forbidden page
   - Network error handling
   - Retry mechanisms

3. **Accessibility**
   - ARIA labels
   - Keyboard navigation
   - Screen reader support
   - Color contrast

4. **Responsive Design**
   - Mobile-friendly layouts
   - Tablet optimization
   - Touch interactions

5. **Testing**
   - Unit tests for composables
   - Component tests
   - E2E tests (optional)

6. **Documentation**
   - Component documentation
   - API integration guide
   - Deployment instructions

#### Deliverables:
- ✅ Optimized production build
- ✅ Comprehensive error handling
- ✅ Accessible UI
- ✅ Mobile responsive
- ✅ Documentation complete

---

## 🔐 Security Considerations

### Authentication
- ✅ JWT tokens stored in HttpOnly cookies or memory (not localStorage for production)
- ✅ Automatic token refresh before expiration
- ✅ Secure logout (clear tokens, blacklist on server)
- ✅ CSRF protection

### Authorization
- ✅ Route-level guards
- ✅ Component-level permission checks
- ✅ API call authorization
- ✅ Hide unauthorized UI elements

### Data Protection
- ✅ HTTPS only in production
- ✅ Input sanitization
- ✅ XSS prevention
- ✅ CORS configuration

---

## 🎨 UI/UX Guidelines

### Design System
- **Primary Color**: Follow existing brand colors
- **Typography**: Consistent font sizes and weights
- **Spacing**: 8px grid system
- **Shadows**: Subtle elevation for cards
- **Border Radius**: Consistent rounding (4-8px)

### Component Standards
- Single responsibility principle
- Props validation with TypeScript
- Emit events for parent communication
- Slots for content flexibility
- Documented props and events

### User Experience
- Loading states for all async operations
- Optimistic updates where appropriate
- Clear error messages
- Confirmation for destructive actions
- Undo functionality where possible
- Keyboard shortcuts for power users

---

## 📊 Migration Strategy

### Phase 2A: Foundation (Days 1-4)
- Setup Vue 3 project
- Core infrastructure (API, router, stores)
- Authentication flow

### Phase 2B: Features (Days 5-8)
- Migrate existing pages
- Component development
- Feature parity with current HTML

### Phase 2C: Advanced (Days 9-10)
- RBAC integration
- Admin features
- Optimization and polish

### Parallel Development
- Keep existing HTML functional during development
- Deploy Vue app to `/app` subdirectory initially
- Gradual migration of traffic
- Final cutover when ready

---

## 🧪 Testing Strategy

### Unit Tests
- Composables (useAuth, usePermission, etc.)
- Utility functions
- Store actions

### Component Tests
- Form validation
- User interactions
- Conditional rendering

### E2E Tests (Optional)
- Login flow
- CRUD operations
- Permission checks

### Tools
- **Vitest**: Unit testing
- **Vue Test Utils**: Component testing
- **Playwright/Cypress**: E2E testing

---

## 🚀 Deployment

### Development
```bash
npm run dev
```

### Production Build
```bash
npm run build
```

### Docker Integration
```dockerfile
# Multi-stage build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Environment Variables
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE=PR Ledger
VITE_APP_VERSION=2.0.0
```

---

## 📈 Success Metrics

### Technical
- ✅ Lighthouse score > 90
- ✅ Bundle size < 500KB (gzipped)
- ✅ First contentful paint < 2s
- ✅ Time to interactive < 3s

### Functional
- ✅ All existing features working
- ✅ Authentication flow complete
- ✅ RBAC fully integrated
- ✅ i18n support maintained

### Quality
- ✅ Zero TypeScript errors
- ✅ ESLint warnings = 0
- ✅ Test coverage > 70%
- ✅ No console errors

---

## ⚠️ Risks & Mitigation

### Risk 1: Learning Curve
**Mitigation**: Use familiar patterns, provide examples, pair programming

### Risk 2: Time Overrun
**Mitigation**: Prioritize core features, defer nice-to-haves, daily standups

### Risk 3: Breaking Existing Functionality
**Mitigation**: Keep old HTML until new app is stable, gradual rollout

### Risk 4: Performance Issues
**Mitigation**: Regular performance testing, code splitting, lazy loading

---

## 📝 Next Steps After Phase 2

### Phase 3: Enhancements
- Real-time notifications (WebSocket)
- Advanced analytics dashboard
- Bulk operations
- Custom reports

### Phase 4: Enterprise Features
- SSO integration (OAuth2/SAML)
- LDAP/AD sync
- Advanced audit trail
- Compliance reporting

### Phase 5: Mobile App
- React Native or Flutter
- Push notifications
- Offline support

---

## 👥 Team Roles

- **Frontend Developer**: Vue implementation, component development
- **Backend Developer**: API adjustments if needed
- **Designer**: UI/UX review, design system
- **QA Engineer**: Testing, bug reporting
- **DevOps**: CI/CD pipeline, deployment

---

## 📚 Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [Vue Router Guide](https://router.vuejs.org/)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Element Plus](https://element-plus.org/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Vite Guide](https://vitejs.dev/guide/)

---

**Status**: 📋 Planning Complete - Ready for Implementation  
**Start Date**: TBD  
**Estimated Duration**: 10 days  
**Priority**: High
