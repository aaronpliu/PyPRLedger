# Logging Configuration Guide

## Overview
The application uses a centralized logging configuration system with daily log rotation and 30-day retention.

## Configuration Files

### 1. `src/conf/logging.yaml`
Main logging configuration file that defines:
- Log formatters (default and detailed)
- Log handlers (console, file, error_file)
- Log levels for different components
- Log rotation settings

### 2. `src/utils/log.py`
Logging utility module providing:
- `setup_logging()`: Initialize logging from YAML config
- `get_logger(name)`: Get configured logger instance
- Automatic `.env` file loading
- Log directory creation

## Features

### Log Rotation
- **Frequency**: Daily (every 24 hours)
- **Retention**: 30 days
- **Files**:
  - `logs/app.log`: All INFO and above logs
  - `logs/error.log`: ERROR level logs only

### Log Format
**Console Output:**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**File Output:**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]
```

### Example Output
```
2026-03-21 22:46:55 - src.main - INFO - Starting application... - [main.py:34]
2026-03-21 22:46:55 - src.core.database - INFO - Database connection initialized successfully - [database.py:93]
```

## Usage

### In main.py
```python
from src.utils.log import setup_logging, get_logger

# Initialize logging system
setup_logging()
logger = get_logger(__name__)

# Use logger
logger.info("Application started")
logger.error("An error occurred")
```

### In Other Modules
```python
from src.utils.log import get_logger

logger = get_logger(__name__)

def my_function():
    logger.debug("Debug information")
    logger.info("Process started")
    logger.warning("Warning message")
    logger.error("Error occurred")
    logger.critical("Critical error")
```

## Configuration Options

### Custom Config Path
```python
setup_logging(config_path="/custom/path/to/logging.yaml")
```

### Custom Env File
```python
setup_logging(env_file="/custom/path/.env")
```

## Log Levels by Component

| Component | Level | Handlers |
|-----------|-------|----------|
| Root | DEBUG | console, file, error_file |
| uvicorn | INFO | console, file, error_file |
| uvicorn.error | INFO | console, file, error_file |
| uvicorn.access | INFO | console, file |
| sqlalchemy | WARNING | console, file, error_file |
| Application | DEBUG | console, file, error_file |

## Dependencies

- `pyyaml>=6.0`: YAML configuration parsing
- `python-dotenv>=1.2.2`: Environment variable loading

## Log Directory Structure

```
project-root/
├── logs/
│   ├── app.log          # Main application log
│   └── error.log        # Error-only log
└── src/
    ├── conf/
    │   └── logging.yaml # Log configuration
    └── utils/
        └── log.py       # Logging utilities
```

## Maintenance

### Manual Log Cleanup
Logs are automatically rotated and kept for 30 days. To manually clean up:
```bash
# Remove logs older than 30 days
find logs/ -name "*.log.*" -mtime +30 -delete
```

### Log Analysis
```bash
# Count errors in error.log
grep -c "ERROR" logs/error.log

# View recent errors
tail -100 logs/error.log

# Search for specific patterns
grep "pattern" logs/app.log
```

## Best Practices

1. **Use appropriate log levels**:
   - `DEBUG`: Detailed technical information for debugging
   - `INFO`: Normal operational messages
   - `WARNING`: Unexpected but handled situations
   - `ERROR`: Serious problems that prevent normal operation
   - `CRITICAL`: Severe errors requiring immediate attention

2. **Include context**: Always provide meaningful messages with relevant details

3. **Use structured logging**: Include request IDs, user IDs, etc. when applicable

4. **Avoid sensitive data**: Never log passwords, tokens, or personal information

5. **Performance consideration**: Avoid excessive logging in hot paths

## Troubleshooting

### Logs not appearing
1. Check log directory permissions: `ls -la logs/`
2. Verify logging.yaml syntax
3. Ensure `setup_logging()` is called before using logger

### Too much logging
1. Increase log level in `logging.yaml`
2. Reduce DEBUG statements in code

### Too little logging
1. Decrease log level in `logging.yaml`
2. Check handler configuration
3. Verify logger names match configuration
