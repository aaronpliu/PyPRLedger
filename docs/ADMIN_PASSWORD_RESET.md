# Admin Password Reset Feature

## Overview

This feature allows system administrators to reset user passwords and force users to change their password on next login. This is useful when:
- A user forgets their password and there's no email/phone verification system
- Initial account setup for new users
- Security incidents requiring password resets

## How It Works

### For Administrators

1. **Navigate to User Management**
   - Go to Admin Panel → Users

2. **Reset User Password**
   - Find the user in the list
   - Click the "Reset Password" button in the Actions column
   - Enter a new initial password (minimum 8 characters)
   - Check "Require user to change password on next login" (enabled by default)
   - Click "Reset Password"

3. **Share Initial Password**
   - Securely share the initial password with the user through a safe channel
   - Inform them they'll need to change it on first login

### For Users

1. **Login with Initial Password**
   - Use the username and initial password provided by the administrator

2. **Force Password Change**
   - System automatically redirects to password change page
   - Enter a new password (minimum 8 characters)
   - Confirm the new password
   - Click "Update Password"

3. **Continue Normal Usage**
   - After successful password change, redirected to Dashboard
   - Can now use the system normally

## Technical Details

### Database Schema

```sql
ALTER TABLE auth_user 
ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
```

### API Endpoints

#### Admin Reset Password
```
POST /api/v1/auth/users/{auth_user_id}/reset-password
```

**Request Body:**
```json
{
  "new_password": "InitialPassword123",
  "force_change": true
}
```

**Permissions Required:** `manage users`

**Response:**
```json
{
  "message": "Password reset successfully"
}
```

#### User Change Password
```
POST /api/v1/auth/change-password
```

**Request Body:**
```json
{
  "old_password": "",  // Ignored when must_change_password is true
  "new_password": "NewSecurePassword123"
}
```

**Note:** When `must_change_password` is true, the old password verification is skipped.

### Frontend Routes

- `/force-password-change` - Forced password change page (only accessible when must_change_password=true)

### Security Features

1. **Permission Control**: Only users with `manage users` permission can reset passwords
2. **Password Strength**: Minimum 8 characters required
3. **Automatic Flag Clearing**: `must_change_password` is automatically set to false after successful password change
4. **Route Protection**: Users cannot access other pages until they change their password
5. **Audit Trail**: All password changes are logged

## Best Practices

1. **Generate Strong Initial Passwords**: Use random, strong passwords for initial setup
2. **Secure Communication**: Share initial passwords through secure channels (not email if possible)
3. **Inform Users**: Let users know they'll need to change the password immediately
4. **Monitor First Login**: Verify that users successfully complete the password change process
5. **Regular Audits**: Periodically review password reset activities in audit logs

## Troubleshooting

### User Cannot Access System After Password Reset

**Problem**: User reports being stuck on the password change page

**Solution**: 
- Ensure they're using the correct initial password
- Check that their account is active (`is_active = true`)
- Verify `must_change_password` flag is set to true in the database

### Admin Cannot Reset Password

**Problem**: "Reset Password" button not visible or returns 403 error

**Solution**:
- Verify admin has `manage users` permission
- Check RBAC role assignments for the admin user
- Ensure the target user exists and is accessible

### Password Change Fails

**Problem**: User receives error when trying to change password

**Solution**:
- Verify new password meets minimum length requirement (8 characters)
- Check that both password fields match
- Review backend logs for specific error messages
- Ensure the user's session is still valid

## Migration Notes

The database migration (`016_add_must_change_password.py`) adds the `must_change_password` column with a default value of `false`, so existing users will not be affected. Only users whose passwords are reset by administrators will have this flag set to `true`.
