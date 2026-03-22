# Author: Aaron Liu

"""
Offline commit message validator.
Enforces:
- Not empty
- At least 10 characters
- Starts with lowercase letter or digit (avoids "Fixed..." etc.)
- Optional: basic Conventional Commits pattern
"""

import re
import sys


def main():
    if len(sys.argv) < 2:
        print("❌ ERROR: Missing commit message file path as argument.")
        sys.exit(1)

    commit_msg_file = sys.argv[1]
    with open(commit_msg_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Get first non-comment, non-empty line
    msg = ""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            msg = stripped
            break

    if not msg:
        print("❌ ERROR: Commit message is empty.")
        sys.exit(1)

    if len(msg) < 10:
        print("❌ ERROR: Commit message too short (<10 characters).")
        sys.exit(1)

    # Require format: word: description (e.g., "feat: add X", "fix: resolve Y")
    # Allow scopes: "fix(auth): ..."
    pattern = r"^[a-z]+(\([a-zA-Z0-9_-]+\))?: [A-Za-z0-9].{5,}$"
    if not re.match(pattern, msg):
        print("⚠️  WARNING: Commit should follow 'type(scope): description' format.")
        print("   Examples:")
        print("     feat: add user login")
        print("     fix(auth): handle token expiry")
        print("     docs: update installation guide")
        # Do NOT exit(1) — treat as warning only
        # Change to sys.exit(1) if you want to enforce strictly
        return

    print("✅ Commit message OK.")


if __name__ == "__main__":
    main()
