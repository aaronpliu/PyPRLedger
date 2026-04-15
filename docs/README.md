Welcome to the PRLedger documentation directory. This folder contains comprehensive guides and technical documentation for the project.

**Latest Release**: API 1.6.0 and UI 1.1.0 (April 2026)

## 📚 Available Documentation

### Getting Started

- **[README.md](../README.md)** - Main project documentation and quick start guide
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and release notes
- **What's New in v1.6.0?** - See [CHANGELOG.md](../CHANGELOG.md#160---2026-04-13) for multi-reviewer review architecture and assignment workflow updates

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

## 🎯 What's New in v1.6.0?

The v1.6.0 API release and v1.1.0 UI release focus on the new multi-reviewer review model and assignment workflow:

### Key Features
- **Multi-Reviewer Review Architecture**: Review data now separates shared PR review state from reviewer assignments
- **Task Assignment Workflow**: Review admins can assign reviewers cleanly against the new base plus assignment model
- **Role Delegation**: Delegated permissions support reviewer and admin workflows with audit coverage
- **Version Visibility**: UI now displays backend and frontend release versions consistently

### Technical Highlights
- Backend schema refactor to `pull_request_review_base` and `pull_request_review_assignment`
- Alembic coverage for multi-reviewer and assignment permissions through migration 012
- Vue frontend task-assignment and delegation management enhancements
- Release metadata aligned across backend, frontend, and docs

See [CHANGELOG.md](../CHANGELOG.md#160---2026-04-13) for complete details.

## 📖 Quick Links

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Start here for installation and usage |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Production deployment instructions |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Understand the codebase layout |
| [VERSIONING.md](VERSIONING.md) | Learn how to manage releases |
| [FastAPI_code_review_system_design.md](FastAPI_code_review_system_design.md) | Deep dive into system architecture |
| [CHANGELOG.md](../CHANGELOG.md) | Latest features and bug fixes (v1.6.0 / UI 1.1.0 released) |

## 🔗 External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

---

**Last Updated**: April 2026  
**Backend Version**: 1.6.0 (see [pyproject.toml](../pyproject.toml)) or run `python scripts/bump_version.py show`  
**Frontend Version**: 1.1.0 (see [frontend/package.json](../frontend/package.json))
