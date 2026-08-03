name: Bug Report
description: Report a bug or unexpected behavior
title: "[Bug]: "
labels: ["bug", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to report a bug! Please fill in the sections below.

  - type: textarea
    id: description
    attributes:
      label: Description
      description: A clear and concise description of the bug.
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the behavior.
      placeholder: |
        1. Go to '...'
        2. Click on '...'
        3. Scroll to '...'
        4. See error
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What you expected to happen.
    validations:
      required: true

  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior
      description: What actually happened. Include screenshots or logs if applicable.
    validations:
      required: true

  - type: dropdown
    id: area
    attributes:
      label: Area
      description: Which part of the system is affected?
      options:
        - Backend (API)
        - Frontend (UI)
        - Database / Migrations
        - Authentication / Session
        - Git Provider Integration
        - SSE / Notifications
        - Docker / Deployment
        - Other
    validations:
      required: true

  - type: input
    id: version
    attributes:
      label: Version
      description: What version of PRLedger are you running?
      placeholder: "e.g. 1.20.4"

  - type: textarea
    id: logs
    attributes:
      label: Logs / Screenshots
      description: Paste any relevant logs or screenshots here (omit sensitive data).
      render: shell

  - type: checkboxes
    id: terms
    attributes:
      label: Checklist
      options:
        - label: I have searched existing issues to avoid duplicates
          required: true
        - label: I have removed any sensitive information from logs/screenshots
          required: true
