# Offline Deployment Guide

## 📦 Localized Dependency Management

This project has localized third-party frontend libraries to support fully offline environment deployment.

### Localized Libraries

#### diff2html (v3.4.45)
- **Location**: `web/lib/`
- **Files**:
  - `diff2html.min.css` (17KB) - Stylesheet
  - `diff2html-ui.min.js` (988KB) - JavaScript library
- **Purpose**: Professional Git diff rendering (GitHub/GitLab style)

---

## 🚀 Deployment Steps

### 1. Clone/Copy Project

```bash
# Clone from Git repository
git clone <repository-url>
cd PyPRLedger

# Or copy the entire project directory
cp -r PyPRLedger /path/to/offline/server
```

### 2. Verify Local Library Files

Ensure the `web/lib/` directory contains the following files:

```bash
ls -lh web/lib/
```

Expected output:
```
-rw-r--r--  diff2html.min.css   (~17KB)
-rw-r--r--  diff2html-ui.min.js (~988KB)
```

### 3. Start Web Server

```bash
# Method 1: Python built-in server (development/testing)
cd web
python3 -m http.server 8080

# Method 2: Nginx (recommended for production)
# Configure Nginx to point to the web/ directory
```

### 4. Access Application

Open browser and visit: `http://localhost:8080/index.html`

---

## 🔄 Update Local Libraries

### Method 1: Use Automated Script (Recommended)

```bash
# Update to latest version
./scripts/update_diff2html.sh

# Update to specific version
./scripts/update_diff2html.sh 3.4.45
```

### Method 2: Manual Download

```bash
cd web/lib

# Download CSS
curl -o diff2html.min.css \
  https://cdn.jsdelivr.net/npm/diff2html@3.4.45/bundles/css/diff2html.min.css

# Download JS
curl -o diff2html-ui.min.js \
  https://cdn.jsdelivr.net/npm/diff2html@3.4.45/bundles/js/diff2html-ui.min.js
```

### Method 3: Copy from Another Environment

If you have an internet-connected environment:
```bash
# Download on internet-connected machine
cd web/lib
curl -O https://cdn.jsdelivr.net/npm/diff2html@3.4.45/bundles/css/diff2html.min.css
curl -O https://cdn.jsdelivr.net/npm/diff2html@3.4.45/bundles/js/diff2html-ui.min.js

# Copy to offline environment
scp web/lib/* user@offline-server:/path/to/PyPRLedger/web/lib/
```

---

## ✅ Verify Offline Availability

### Testing Steps

1. **Disconnect Network**
   ```bash
   # macOS
   networksetup -setairportpower en0 off
   
   # Linux
   nmcli radio wifi off
   ```

2. **Clear Browser Cache**
   - Chrome: `Ctrl+Shift+Delete` → Clear cache
   - Firefox: `Ctrl+Shift+Delete` → Clear cache

3. **Access Application**
   - Open `http://localhost:8080/index.html`
   - Check if code diff displays correctly
   - Switch between Unified/Side-by-Side views

4. **Check Browser Console**
   - Press `F12` to open Developer Tools
   - View Network tab
   - Confirm all resources show status as `(disk cache)` or `(memory cache)`
   - No red errors

5. **Restore Network**
   ```bash
   # macOS
   networksetup -setairportpower en0 on
   
   # Linux
   nmcli radio wifi on
   ```

---

## 📋 File Checklist

### Files That Must Be Committed to Git

```
web/lib/
├── diff2html.min.css      # ✅ Required
├── diff2html-ui.min.js    # ✅ Required
└── README.md              # ✅ Documentation
```

### .gitignore Configuration

Exception rule configured to track `web/lib/`:

```gitignore
lib/
!web/lib/
```

---

## 🔧 Troubleshooting

### Issue 1: File Not Found (404)

**Symptoms**: Browser console shows 404 error for `diff2html.min.css` or `diff2html-ui.min.js`

**Solution**:
```bash
# Check if files exist
ls -lh web/lib/

# If missing, re-download
./scripts/update_diff2html.sh 3.4.45
```

### Issue 2: Style Issues

**Symptoms**: Diff displays but styles are incorrect

**Solution**:
1. Clear browser cache
2. Hard refresh page (`Ctrl+F5` or `Cmd+Shift+R`)
3. Check CSS file integrity:
   ```bash
   # Check file size (should be ~17KB)
   ls -lh web/lib/diff2html.min.css
   ```

### Issue 3: JavaScript Errors

**Symptoms**: Console shows `Diff2HtmlUI is not defined`

**Solution**:
1. Check if JS file is loaded:
   ```bash
   ls -lh web/lib/diff2html-ui.min.js
   ```
2. Check HTML reference path:
   ```html
   <script src="lib/diff2html-ui.min.js"></script>
   ```
3. Re-download files:
   ```bash
   ./scripts/update_diff2html.sh
   ```

### Issue 4: Git Not Tracking lib Files

**Symptoms**: `git status` doesn't show files in `web/lib/`

**Solution**:
```bash
# Check .gitignore configuration
cat .gitignore | grep "web/lib"

# Force add
git add -f web/lib/
git commit -m "Add diff2html library files"
```

---

## 📊 File Size Reference

| File | Size | Compressed |
|------|------|------------|
| `diff2html.min.css` | ~17 KB | ~4 KB (gzip) |
| `diff2html-ui.min.js` | ~988 KB | ~280 KB (gzip) |
| **Total** | **~1 MB** | **~284 KB** |

---

## 🔐 Security Recommendations

### 1. File Integrity Verification

Regularly verify file hashes:

```bash
# Generate current hashes
cd web/lib
sha256sum diff2html.min.css diff2html-ui.min.js > checksums.sha256

# Verify file integrity
sha256sum -c checksums.sha256
```

### 2. Version Locking

In production environments, always use fixed versions to avoid automatic updates:

```html
<!-- ✅ Recommended: Fixed version -->
<script src="lib/diff2html-ui.min.js"></script>

<!-- ❌ Avoid: CDN dynamic version -->
<script src="https://cdn.jsdelivr.net/npm/diff2html/bundles/js/diff2html-ui.min.js"></script>
```

### 3. Backup Strategy

Regularly backup the `web/lib/` directory:

```bash
# Create backup
tar -czf web-lib-backup-$(date +%Y%m%d).tar.gz web/lib/

# Restore to another environment
tar -xzf web-lib-backup-20260405.tar.gz -C /path/to/target/
```

---

## 📝 Maintenance Log

| Date | Action | Version | Notes |
|------|--------|---------|-------|
| 2026-04-05 | Initial addition | 3.4.45 | Offline environment support |

---

## 💡 Best Practices

1. **Always Use Local Files**
   - Don't mix CDN and local resources
   - Keep reference paths consistent

2. **Version Management**
   - Test new version compatibility before updating
   - Record changes in CHANGELOG

3. **Documentation Synchronization**
   - Update this document when updating libraries
   - Record known issues and solutions

4. **Team Collaboration**
   - Explain local library location during onboarding
   - Check lib file changes during code review

---

## 🔗 Related Resources

- [diff2html Official Documentation](https://github.com/rtfpessoa/diff2html)
- [jsDelivr CDN](https://www.jsdelivr.com/package/npm/diff2html)
- [Project Web Directory Structure](../docs/PROJECT_STRUCTURE.md)
