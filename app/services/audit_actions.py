"""Audit action enum."""

# Profile lifecycle
PROFILE_CREATED = "profile_created"
PROFILE_EDITED = "profile_edited"
PROFILE_DELETED = "profile_deleted"

# Deployment
DEPLOY_STARTED = "deploy_started"
DEPLOY_SUCCEEDED = "deploy_succeeded"
DEPLOY_FAILED = "deploy_failed"

# Auto-deploy
AUTO_DEPLOY_TRIGGERED = "auto_deploy_triggered"
AUTO_DEPLOY_SUCCEEDED = "auto_deploy_succeeded"
AUTO_DEPLOY_FAILED = "auto_deploy_failed"

# App controls
APP_STARTED = "app_started"
APP_STOPPED = "app_stopped"
APP_RESTARTED = "app_restarted"
APP_SCALED = "app_scaled"
APP_ROLLED_BACK = "app_rolled_back"
APP_DELETED = "app_deleted"

# Accounts
ACCOUNT_ADDED = "account_added"
ACCOUNT_REMOVED = "account_removed"

# Health monitoring
DYNO_CRASH_DETECTED = "dyno_crash_detected"
