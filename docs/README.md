Welcome to the PRLedger documentation directory. This folder contains comprehensive guides and technical documentation for the project.

**Latest Version**: 1.5.0 - Vue.js Frontend Application (February 2026)

## 📚 Available Documentation

### Getting Started

- **[README.md](../README.md)** - Main project documentation and quick start guide
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and release notes
- **What's New in v1.5.0?** - See [CHANGELOG.md](../CHANGELOG.md#150---2026-02-xx) for Vue.js Frontend details

### Core Documentation

- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Detailed project structure overview
  - Complete directory layout
  - File descriptions and purposes
  - Key features breakdown including new Project Registry components

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Production deployment instructions
  - Prerequisites and setup
  - Docker deployment
  - Production configuration
  - Monitoring and maintenance
  - Troubleshooting guide

### Technical Documentation

- **[FastAPI_code_review_system_design.md](FastAPI_code_review_system_design.md)** - System architecture and design
  - Database schema design including new `project_registry` table
  - Redis caching strategies
  - Async programming patterns
  - Monitoring with Prometheus/Grafana
  - Performance optimization techniques
  - API design patterns
  - Virtual app_name architecture (NEW in v1.3.0)

### Version Management

- **[VERSIONING.md](VERSIONING.md)** - Complete version management guide
  - How to update versions
  - Semantic versioning explanation
  - Release checklist
  - Troubleshooting

- **[VERSION_MANAGEMENT_SUMMARY.md](VERSION_MANAGEMENT_SUMMARY.md)** - Implementation details
  - Architecture overview
  - Migration notes
  - Benefits and best practices

- **[QUICK_VERSION_REFERENCE.md](QUICK_VERSION_REFERENCE.md)** - Quick reference card
  - Common commands
  - Release checklist
  - Troubleshooting tips

## 🎯 What's New in v1.5.0?

The v1.5.0 release introduces the **Vue.js Frontend Application** - a complete rewrite using modern frameworks:

### Key Features
- **Modern Vue 3 Architecture**: Full TypeScript support with Composition API
- **Enhanced Code Diff Viewer**: Professional Diff2Html integration with side-by-side and unified views
- **Advanced Review Management**: Multi-reviewer tracking, real-time updates, export capabilities
- **Analytics Dashboard**: Interactive charts with ECharts for score analysis and trends

### Technical Highlights
- Build system: Vite 7.3.2 with optimized bundling
- UI framework: Element Plus 2.13.6 with responsive design
- State management: Pinia 3.0.4
- Routing: Vue Router 5.0.4
- Internationalization: Vue I18n 11.3.1
- Fixed critical diff rendering issues (line number scrolling)

See [CHANGELOG.md](../CHANGELOG.md#150---2026-02-xx) for complete details.

## 📖 Quick Links

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Start here for installation and usage |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Production deployment instructions |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Understand the codebase layout |
| [VERSIONING.md](VERSIONING.md) | Learn how to manage releases |
| [FastAPI_code_review_system_design.md](FastAPI_code_review_system_design.md) | Deep dive into system architecture |
| [CHANGELOG.md](../CHANGELOG.md) | Latest features and bug fixes (v1.5.0 released!) |

## 🔗 External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

---

**Last Updated**: February 2026  
**Backend Version**: 1.5.0 (see [pyproject.toml](../pyproject.toml)) or run `python scripts/bump_version.py show`  
**Frontend Version**: 1.0.0 (see [frontend/package.json](../frontend/package.json))
