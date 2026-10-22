# Frontend Environment Configuration

This project supports multiple environments for different deployment scenarios.

## Environment Files

| File | Mode | Description | API Endpoint |
|------|------|-------------|--------------|
| `.env` | (default) | Local development | `http://127.0.0.1:9097/api/v1` |
| `.env.test` | test | Test/Staging environment | `http://127.0.0.1:3000/api/v1` |
| `.env.prod` | prod | Production environment | `https://api.prledger.com/api/v1` |

## Available Commands

### Development

```bash
# Local development (uses .env)
npm run dev

# Test environment development (uses .env.test)
npm run dev:test

# Production environment development (uses .env.prod)
npm run dev:prod
```

### Build

```bash
# Build for production (default, uses .env)
npm run build

# Build for test environment (uses .env.test)
npm run build:test

# Build for production environment (uses .env.prod)
npm run build:prod
```

### Preview

```bash
# Preview production build
npm run preview

# Preview test build
npm run preview:test

# Preview prod build
npm run preview:prod
```

## Environment Variables

### Required Variables

- `VITE_API_DOMAIN`: Backend API domain URL
- `VITE_API_BASE_PATH`: API base path (default: `/api/v1`)
- `VITE_API_BASE_URL`: Full backend API base URL
- `VITE_DEV_PORT`: Development server port
- `VITE_APP_TITLE`: Application title
- `VITE_APP_VERSION`: Application version
- `VITE_JWT_STORAGE_KEY`: LocalStorage key for JWT tokens

### Optional Variables

- `VITE_ENABLE_ANALYTICS`: Enable/disable analytics tracking (default: false)
- `VITE_ENABLE_DEBUG`: Enable/disable debug mode (default: false)
- `VITE_ENABLE_HTTPS`: Force HTTPS in production (default: false)

## Usage in Code

Access environment variables in your code:

```typescript
// API configuration
const apiDomain = import.meta.env.VITE_API_DOMAIN
const apiBasePath = import.meta.env.VITE_API_BASE_PATH
const apiBase = import.meta.env.VITE_API_BASE_URL

// Dev server
const devPort = import.meta.env.VITE_DEV_PORT

// Feature flags
const enableAnalytics = import.meta.env.VITE_ENABLE_ANALYTICS === 'true'
const enableDebug = import.meta.env.VITE_ENABLE_DEBUG === 'true'
const enableHttps = import.meta.env.VITE_ENABLE_HTTPS === 'true'

// App info
const appTitle = import.meta.env.VITE_APP_TITLE
const appVersion = import.meta.env.VITE_APP_VERSION

// Auth
const jwtStorageKey = import.meta.env.VITE_JWT_STORAGE_KEY
```

## Deployment Workflow

1. **Local Development**: Use `npm run dev` with `.env`
2. **Test Deployment**: Run `npm run build:test` and deploy the `dist/` folder
3. **Production Deployment**: Run `npm run build:prod` and deploy the `dist/` folder

### Replacing a build that is already being used

Every asset is named after its own content, so a new build replaces all chunk
filenames at once. Copy the new `dist/` over the served directory without emptying
it first: a tab that was open during the deploy still names the chunks of the build
before it, and deleting them turns its next click into a 404. When the app meets
such a missing chunk it tells the reader a new version is available and offers to
reload, which only helps if the files the new `index.html` names are there.

Serve `index.html` with `no-cache`, and `/assets/` as `immutable` - but answer a
missing file under `/assets/` as a 404, never with the SPA fallback. The browser
would take that HTML for a module and fail to execute it.

## Notes

- Never commit sensitive data (API keys, secrets) to `.env` files
- Use environment-specific secrets management for production
- The `.env` file is gitignored by default
- Example: Copy `.env.example` to `.env` and modify as needed
