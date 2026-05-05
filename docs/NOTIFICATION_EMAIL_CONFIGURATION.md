# Notification & Email Configuration Guide

This guide explains how to configure the notification system and email delivery for PyPRLedger.

---

## 📋 Overview

The notification system supports multiple delivery channels:
- ✅ **In-App Notifications** (default, always enabled)
- 📧 **Email Notifications** (requires SMTP configuration)
- 💬 **Slack Notifications** (requires webhook configuration)

---

## ⚙️ Configuration Settings

All settings are configured in your `.env` file. Copy from `.env.example` and customize.

### **1. Notification Settings**

```bash
# How long to keep notifications before auto-deletion (days)
NOTIFICATION_RETENTION_DAYS=30

# Enable/disable daily digest emails (future feature)
NOTIFICATION_DIGEST_ENABLED=True

# Digest frequency: daily, weekly, monthly
NOTIFICATION_DIGEST_FREQUENCY=daily

# Maximum notifications per user per day (rate limiting)
NOTIFICATION_MAX_PER_DAY=100
```

**Recommendations**:
- `NOTIFICATION_RETENTION_DAYS`: 30 days is good for most systems
- `NOTIFICATION_MAX_PER_DAY`: Adjust based on your team size and activity
  - Small team (5-10): 50-100
  - Medium team (10-50): 100-200
  - Large team (50+): 200-500

---

### **2. Email (SMTP) Configuration**

To enable email notifications, configure your SMTP server:

```bash
# SMTP Server Settings
SMTP_HOST=smtp.gmail.com          # Your SMTP server hostname
SMTP_PORT=587                     # Port (587 for TLS, 465 for SSL)
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password   # Use app password, not regular password
EMAIL_FROM=noreply@yourdomain.com
EMAIL_FROM_NAME=PyPRLedger Notifications

# Security Settings
SMTP_USE_TLS=True                 # Use TLS encryption (recommended)
SMTP_USE_SSL=False                # Use SSL instead of TLS (alternative)
```

#### **Common SMTP Providers**

**Gmail**:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```
⚠️ **Important**: You must use an [App Password](https://myaccount.google.com/apppasswords), not your regular password.

**Outlook/Office 365**:
```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

**AWS SES**:
```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

**SendGrid**:
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey              # Literally "apikey"
SMTP_PASSWORD=your_sendgrid_api_key
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

**Custom SMTP Server**:
```bash
SMTP_HOST=mail.yourcompany.com
SMTP_PORT=587
SMTP_USERNAME=notifications@yourcompany.com
SMTP_PASSWORD=your_password
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

---

### **3. Slack Integration**

To enable Slack notifications, create a webhook:

```bash
# Slack Webhook URL (from Slack Incoming Webhooks app)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_SLACK_WEBHOOK_URL

# Enable/disable Slack notifications
SLACK_ENABLED=True
```

#### **Setup Steps**:

1. **Create Incoming Webhook**:
   - Go to [Slack API Apps](https://api.slack.com/apps)
   - Click "Create New App" → "From scratch"
   - Name it "PyPRLedger Notifications"
   - Select your workspace

2. **Activate Incoming Webhooks**:
   - Go to "Incoming Webhooks" in sidebar
   - Toggle "Activate Incoming Webhooks" to On
   - Click "Add New Webhook to Workspace"
   - Select the channel where notifications should go
   - Copy the webhook URL

3. **Configure in .env**:
   ```bash
   SLACK_WEBHOOK_URL=<paste the URL here>
   SLACK_ENABLED=True
   ```

---

## 🔧 Testing Configuration

### **Test Email Delivery**

Once SMTP is configured, test it:

```python
# Create a test script: scripts/test_email.py
import asyncio
import aiosmtplib
from src.core.config import settings

async def test_smtp():
    """Test SMTP connection"""
    try:
        message = f"""\
Subject: Test Email from PyPRLedger
From: {settings.EMAIL_FROM}
To: test@example.com

This is a test email from PyPRLedger notification system.
If you receive this, SMTP is configured correctly!
"""
        
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
        )
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

asyncio.run(test_smtp())
```

Run with:
```bash
uv run python scripts/test_email.py
```

### **Test Slack Webhook**

```bash
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test notification from PyPRLedger!"}' \
  $SLACK_WEBHOOK_URL
```

If successful, you'll see the message in your Slack channel.

---

## 📊 Current Status

| Feature | Status | Notes |
|---------|--------|-------|
| In-App Notifications | ✅ Working | Default, no config needed |
| Email Notifications | ⏳ Ready | Requires SMTP config |
| Slack Notifications | ⏳ Ready | Requires webhook config |
| Daily Digest | ⏳ Planned | Future enhancement |
| Browser Push | ⏳ Planned | Future enhancement |

---

## 🚀 Enabling Email/Slack Notifications

Currently, the system only sends **in-app notifications**. To enable email/Slack:

1. **Configure SMTP/Slack** in `.env` (as shown above)
2. **Update notification service** to check preferences and send via configured channels
3. **Restart backend server**:
   ```bash
   uv run uvicorn src.main:app --reload
   ```

**Note**: The notification preference system is already in place. Users can configure their preferences at `/notifications/preferences` once email/Slack integration is fully implemented.

---

## 🔒 Security Best Practices

### **SMTP Credentials**
- ✅ Use environment variables (`.env` file)
- ✅ Never commit `.env` to version control
- ✅ Use app passwords, not main account passwords
- ✅ Rotate passwords regularly
- ❌ Don't hardcode credentials in code

### **Slack Webhooks**
- ✅ Keep webhook URLs secret
- ✅ Use dedicated channels for notifications
- ✅ Regularly rotate webhooks if compromised
- ❌ Don't share webhook URLs publicly

---

## 🐛 Troubleshooting

### **Email Not Sending**

**Problem**: "Connection refused" or "Timeout"
```bash
# Check if SMTP server is reachable
telnet smtp.gmail.com 587

# Verify firewall isn't blocking
nc -zv smtp.gmail.com 587
```

**Problem**: "Authentication failed"
- Double-check username/password
- For Gmail, ensure you're using an [App Password](https://myaccount.google.com/apppasswords)
- Verify 2FA is enabled (required for Gmail app passwords)

**Problem**: "TLS/SSL error"
- Try switching between TLS and SSL
- Check if your SMTP server requires specific security settings

### **Slack Not Receiving Messages**

**Problem**: Webhook returns error
```bash
# Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test"}' \
  https://hooks.slack.com/services/YOUR_SLACK_WEBHOOK_URL
```

**Problem**: Messages not appearing in channel
- Verify webhook is added to the correct channel
- Check if channel still exists
- Ensure bot has permission to post

---

## 📝 Example Configurations

### **Development (Local)**
```bash
# No email/Slack - just in-app notifications
SMTP_HOST=
SLACK_ENABLED=False
```

### **Staging**
```bash
# Test email with Mailhog or similar
SMTP_HOST=localhost
SMTP_PORT=1025
EMAIL_FROM=test@staging.example.com
SLACK_ENABLED=False
```

### **Production**
```bash
# Full email and Slack integration
NOTIFICATION_RETENTION_DAYS=90
NOTIFICATION_MAX_PER_DAY=200

SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=SG.xxxxxxxxxxxxx
EMAIL_FROM=noreply@yourcompany.com
EMAIL_FROM_NAME=Your Company PR Ledger
SMTP_USE_TLS=True

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_SLACK_WEBHOOK_URL
SLACK_ENABLED=True
```

---

## 🔗 Related Documentation

- [Phase 4 Implementation Report](./PHASE4_COMPLETE_IMPLEMENTATION_REPORT.md)
- [Notification API Documentation](../src/api/v1/endpoints/notifications.py)
- [Configuration Reference](../src/core/config.py)

---

## ❓ Need Help?

If you encounter issues:
1. Check backend logs: `docker-compose logs -f api | grep -i notification`
2. Verify environment variables are loaded: `echo $SMTP_HOST`
3. Test with the debug scripts provided above
4. Review the troubleshooting section

---

**Last Updated**: May 2026  
**Version**: Phase 4 - Notification System
