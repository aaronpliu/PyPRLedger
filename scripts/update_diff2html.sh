#!/bin/bash
# Script to update diff2html library to latest or specified version
# Usage: ./update_diff2html.sh [version]
# Example: ./update_diff2html.sh 3.4.45

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../web/lib"
VERSION="${1:-latest}"

echo "📦 Updating diff2html library..."
echo "   Target directory: $LIB_DIR"

if [ "$VERSION" = "latest" ]; then
    echo "   Version: latest"
    VERSION_URL="https://cdn.jsdelivr.net/npm/diff2html/bundles"
else
    echo "   Version: $VERSION"
    VERSION_URL="https://cdn.jsdelivr.net/npm/diff2html@$VERSION/bundles"
fi

# Create lib directory if it doesn't exist
mkdir -p "$LIB_DIR"

# Download CSS
echo "⬇️  Downloading CSS..."
curl -L -o "$LIB_DIR/diff2html.min.css" "$VERSION_URL/css/diff2html.min.css"

# Download JS
echo "⬇️  Downloading JavaScript..."
curl -L -o "$LIB_DIR/diff2html-ui.min.js" "$VERSION_URL/js/diff2html-ui.min.js"

# Verify downloads
if [ -f "$LIB_DIR/diff2html.min.css" ] && [ -f "$LIB_DIR/diff2html-ui.min.js" ]; then
    echo "✅ Download completed successfully!"
    echo ""
    echo "📊 File sizes:"
    ls -lh "$LIB_DIR/diff2html.min.css" "$LIB_DIR/diff2html-ui.min.js" | awk '{print "   " $9 ": " $5}'
    echo ""
    echo "💡 Remember to commit these changes to git:"
    echo "   git add web/lib/"
    echo "   git commit -m 'Update diff2html to $VERSION'"
else
    echo "❌ Error: One or more files failed to download"
    exit 1
fi
