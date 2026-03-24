import logging
import logging.config
from pathlib import Path

import yaml


def setup_logging(config_path: str | None = None, env_file: str | None = None) -> None:
    """
    Setup logging configuration from YAML file.

    Args:
        config_path: Path to the logging YAML configuration file.
                    If None, defaults to src/conf/logging.yaml
        env_file: Path to .env file for loading environment variables.
                 If None, tries to load from project root

    Example:
        >>> setup_logging()
        >>> logger = get_logger(__name__)
    """
    # Load environment variables if .env file exists
    if env_file is None:
        # Try to find .env file in project root
        project_root = Path(__file__).parent.parent.parent
        env_paths = [
            project_root / ".env",
            project_root / ".env.local",
        ]

        for env_path in env_paths:
            if env_path.exists():
                try:
                    from dotenv import load_dotenv

                    load_dotenv(env_path)
                    break
                except ImportError:
                    # python-dotenv not installed, skip
                    pass

    # Determine config path
    if config_path is None:
        config_path = Path(__file__).parent.parent / "conf" / "logging.yaml"
    else:
        config_path = Path(config_path)

    # Ensure config file exists
    if not config_path.exists():
        raise FileNotFoundError(f"Logging configuration file not found: {config_path}")

    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Load logging configuration
    with Path.open(config_path) as f:
        config = yaml.safe_load(f)

    # Apply configuration
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    return logging.getLogger(name)


def get_configured_logger() -> bool:
    """
    Check if logging has been properly configured.

    Returns:
        True if logging is configured, False otherwise
    """
    root_logger = logging.getLogger()
    return len(root_logger.handlers) > 0
