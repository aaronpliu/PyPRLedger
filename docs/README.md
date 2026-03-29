Welcome to the PRLedger documentation directory. This folder contains comprehensive guides and technical documentation for the project.

**Latest Version**: 1.3.0 - Project Registry System (March 2026)

## 📚 Available Documentation

### Getting Started

- **[README.md](../README.md)** - Main project documentation and quick start guide
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and release notes
- **What's New in v1.3.0?** - See [CHANGELOG.md](../CHANGELOG.md#130---2026-03-29) for Project Registry System details

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

## 🎯 What's New in v1.3.0?

The v1.3.0 release introduces the **Project Registry System** - a revolutionary approach to multi-project management:

### Key Features
- **Virtual App Name Architecture**: Organize projects into logical applications without schema changes
- **Multi-App Query Support**: Filter reviews by multiple apps simultaneously using comma-separated parameters
- **Admin APIs**: Complete CRUD operations for managing project-to-application mappings
- **Enhanced Responses**: All review responses now include complete entity information and virtual `app_name` field

### Architecture Highlights
- Single physical table (`pull_request_review`) stores all review data
- New `project_registry` table maps `(project_key, repository_slug)` pairs to `app_name`
- Query-time resolution of app names via batch lookups
- Default app assignment: "Unknown" for unregistered projects
- Auto-registration mechanism for seamless onboarding

See [CHANGELOG.md](../CHANGELOG.md#130---2026-03-29) for complete details.

## 📖 Quick Links

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Start here for installation and usage |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Production deployment instructions |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Understand the codebase layout |
| [VERSIONING.md](VERSIONING.md) | Learn how to manage releases |
| [FastAPI_code_review_system_design.md](FastAPI_code_review_system_design.md) | Deep dive into system architecture |
| [CHANGELOG.md](../CHANGELOG.md) | Latest features and bug fixes (v1.3.0 released!) |

## 🔗 External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

---

**Last Updated**: March 29, 2026  
**Project Version**: 1.3.0 (see [pyproject.toml](../pyproject.toml)) or run `python scripts/bump_version.py show`
