# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| Latest  | Yes       |

Only the latest release receives security patches. Please upgrade to the latest version before reporting vulnerabilities.

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Please report security issues privately via email to **aaron.p.liu@outlook.com**.

Include the following in your report:

- Description of the vulnerability
- Steps to reproduce or a proof-of-concept
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within **3 business days** and provide a timeline for resolution.

## Security Best Practices for Deployment

- Rotate `SECRET_KEY` regularly and never commit it to version control
- Use strong, unique passwords for database and Redis
- Enable HTTPS/TLS in production
- Restrict Redis and MySQL to internal networks only
- Review and restrict CORS origins in production
- Keep dependencies up to date (`uv lock --upgrade`)
