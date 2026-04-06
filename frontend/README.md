# PR Ledger Frontend - Vue 3 Application

Modern Vue 3 frontend for PR Ledger code review system.

## 🚀 Tech Stack

- **Framework**: Vue 3.4+ (Composition API)
- **Build Tool**: Vite 5.x
- **Language**: TypeScript 5.x
- **State Management**: Pinia 2.x
- **Routing**: Vue Router 4.x
- **UI Framework**: Element Plus 2.x
- **HTTP Client**: Axios 1.x

## 📁 Project Structure

```
frontend/
├── src/
│   ├── api/              # API service layer
│   ├── assets/           # Static assets
│   ├── components/       # Reusable components
│   ├── composables/      # Composition API functions
│   ├── layouts/          # Layout components
│   ├── router/           # Vue Router config
│   ├── stores/           # Pinia stores
│   ├── types/            # TypeScript types
│   ├── utils/            # Utility functions
│   ├── views/            # Page components
│   ├── App.vue           # Root component
│   └── main.ts           # Entry point
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## 🛠️ Development

### Install Dependencies
```bash
npm install
```

### Start Dev Server
```bash
npm run dev
```
Server runs at http://localhost:3000

### Build for Production
```bash
npm run build
```

### Preview Production Build
```bash
npm run preview
```

## 🔧 Configuration

### Environment Variables
Create `.env` file:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE=PR Ledger
```

### Vite Proxy
API requests are proxied to backend:
- Frontend: `http://localhost:3000/api/*`
- Backend: `http://localhost:8000/api/*`

## 📝 Implementation Status

### ✅ Completed (Day 1)
- [x] Vue 3 + Vite + TypeScript setup
- [x] Core dependencies installed
- [x] Project structure created
- [x] Vite configuration (proxy, aliases, code splitting)
- [x] TypeScript strict mode
- [x] Axios request wrapper with interceptors
- [x] Type definitions (User, Auth, RBAC, Audit)
- [x] API services (auth, rbac, audit)
- [x] Pinia auth store
- [x] Vue Router with navigation guards
- [x] Layout components (Default, Admin)
- [x] Login page
- [x] Placeholder views for all routes

### 🚧 In Progress
- [ ] Complete all feature pages
- [ ] RBAC integration
- [ ] i18n support
- [ ] Testing

## 🔐 Authentication Flow

1. User logs in via `/login`
2. JWT tokens stored in localStorage
3. Axios interceptor adds token to requests
4. Router guards protect authenticated routes
5. Auto-redirect on 401 errors

## 📊 State Management

**Pinia Stores**:
- `auth`: User authentication state
- Future: `reviews`, `scores`, `audit`

## 🎨 UI Components

Using **Element Plus** for consistent design:
- Forms and inputs
- Tables and data display
- Notifications and messages
- Icons
- Layout components

## 🌐 API Integration

All API calls go through typed service layers:
```typescript
import { authApi } from '@/api/auth'

// Login
await authApi.login({ username, password })

// Get current user
const user = await authApi.getCurrentUser()
```

## 📱 Responsive Design

- Mobile-friendly layouts
- Tablet optimization
- Desktop-first approach

## 🔮 Next Steps

1. Implement remaining feature pages
2. Add RBAC permission checks
3. Integrate i18n (en, zh-CN, zh-TW)
4. Add comprehensive error handling
5. Write unit tests
6. Optimize performance

## 📚 Resources

- [Vue 3 Docs](https://vuejs.org/)
- [Vite Guide](https://vitejs.dev/)
- [Element Plus](https://element-plus.org/)
- [Pinia](https://pinia.vuejs.org/)
- [Vue Router](https://router.vuejs.org/)

---

**Status**: Phase 2 Day 1 Complete ✅  
**Last Updated**: April 6, 2026
