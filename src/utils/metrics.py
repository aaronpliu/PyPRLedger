import logging
from typing import Dict, List, Optional
from prometheus_client import (
    Counter, 
    Histogram, 
    Gauge, 
    CollectorRegistry, 
    generate_latest, 
    CONTENT_TYPE_LATEST
)
from prometheus_client.openmetrics.exposition import (
    generate_latest as generate_latest_openmetrics
)
from fastapi import Response
import time

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Prometheus metrics collector for code review system"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector
        
        Args:
            registry: Optional custom registry. If not provided, creates a new one.
        """
        self.registry = registry or CollectorRegistry()
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize all Prometheus metrics"""
        # Request metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request latency in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Review metrics
        self.review_total = Counter(
            'review_total',
            'Total number of code reviews',
            ['project', 'reviewer', 'status'],
            registry=self.registry
        )
        
        self.review_duration_seconds = Histogram(
            'review_duration_seconds',
            'Time spent on code review in seconds',
            ['project'],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300],
            registry=self.registry
        )
        
        self.active_reviewers = Gauge(
            'active_reviewers',
            'Number of active reviewers',
            ['project'],
            registry=self.registry
        )
        
        self.review_score = Histogram(
            'review_score',
            'Code review scores',
            ['project'],
            buckets=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            registry=self.registry
        )
        
        # User metrics
        self.users_total = Gauge(
            'users_total',
            'Total number of users',
            registry=self.registry
        )
        
        self.users_active = Gauge(
            'users_active',
            'Number of active users',
            registry=self.registry
        )
        
        self.reviewers_total = Gauge(
            'reviewers_total',
            'Total number of reviewers',
            registry=self.registry
        )
        
        self.reviewers_active = Gauge(
            'reviewers_active',
            'Number of active reviewers',
            registry=self.registry
        )
        
        # Project metrics
        self.projects_total = Gauge(
            'projects_total',
            'Total number of projects',
            registry=self.registry
        )
        
        self.projects_active = Gauge(
            'projects_active',
            'Number of active projects',
            registry=self.registry
        )
        
        # Repository metrics
        self.repositories_total = Gauge(
            'repositories_total',
            'Total number of repositories',
            registry=self.registry
        )
        
        # Pull Request metrics
        self.pull_requests_total = Counter(
            'pull_requests_total',
            'Total number of pull requests',
            ['project', 'status'],
            registry=self.registry
        )
        
        self.pull_requests_open = Gauge(
            'pull_requests_open',
            'Number of open pull requests',
            ['project'],
            registry=self.registry
        )
        
        self.pull_requests_merged = Gauge(
            'pull_requests_merged',
            'Number of merged pull requests',
            ['project'],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_hits_total = Counter(
            'cache_hits_total',
            'Total number of cache hits',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_misses_total = Counter(
            'cache_misses_total',
            'Total number of cache misses',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_errors_total = Counter(
            'cache_errors_total',
            'Total number of cache errors',
            ['cache_type', 'error_type'],
            registry=self.registry
        )
        
        # Database metrics
        self.db_connections_active = Gauge(
            'db_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.db_query_duration_seconds = Histogram(
            'db_query_duration_seconds',
            'Database query duration in seconds',
            ['operation'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5],
            registry=self.registry
        )
        
        self.db_queries_total = Counter(
            'db_queries_total',
            'Total number of database queries',
            ['operation', 'table'],
            registry=self.registry
        )
        
        # System metrics
        self.system_cpu_usage_percent = Gauge(
            'system_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage_bytes = Gauge(
            'system_memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )
        
        self.system_memory_available_bytes = Gauge(
            'system_memory_available_bytes',
            'Available memory in bytes',
            registry=self.registry
        )
        
        self.system_disk_usage_bytes = Gauge(
            'system_disk_usage_bytes',
            'Disk usage in bytes',
            ['path'],
            registry=self.registry
        )
        
        self.system_disk_available_bytes = Gauge(
            'system_disk_available_bytes',
            'Available disk space in bytes',
            ['path'],
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'errors_total',
            'Total number of errors',
            ['type', 'endpoint'],
            registry=self.registry
        )
        
        self.errors_rate_limited_total = Counter(
            'errors_rate_limited_total',
            'Total number of rate limit errors',
            ['endpoint'],
            registry=self.registry
        )
        
        # Business metrics
        self.files_reviewed_total = Counter(
            'files_reviewed_total',
            'Total number of files reviewed',
            ['project'],
            registry=self.registry
        )
        
        self.lines_changed_total = Counter(
            'lines_changed_total',
            'Total number of lines changed in reviews',
            ['project', 'change_type'],
            registry=self.registry
        )
        
        self.review_cycle_time_seconds = Histogram(
            'review_cycle_time_seconds',
            'Time from PR creation to review completion in seconds',
            ['project'],
            buckets=[3600, 7200, 14400, 28800, 43200, 86400, 172800, 259200],
            registry=self.registry
        )
        
        self.pr_merge_time_seconds = Histogram(
            'pr_merge_time_seconds',
            'Time from PR creation to merge in seconds',
            ['project'],
            buckets=[3600, 7200, 14400, 28800, 43200, 86400, 172800, 259200],
            registry=self.registry
        )
        
        self.review_backlog_count = Gauge(
            'review_backlog_count',
            'Number of PRs waiting for review',
            ['project'],
            registry=self.registry
        )
        
        self.reviewers_load = Gauge(
            'reviewers_load',
            'Average number of active PRs per reviewer',
            ['project'],
            registry=self.registry
        )
        
        logger.info("Initialized all Prometheus metrics")
    
    def increment_http_request(self, method: str, endpoint: str, status: int) -> None:
        """
        Increment HTTP request counter
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            status: HTTP status code
        """
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    
    def observe_http_request_duration(self, method: str, endpoint: str, duration: float) -> None:
        """
        Observe HTTP request duration
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            duration: Request duration in seconds
        """
        self.http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    
    def increment_review(
        self,
        project: str,
        reviewer: str,
        status: str = "open"
    ) -> None:
        """
        Increment review counter
        
        Args:
            project: Project identifier
            reviewer: Reviewer identifier
            status: Review status
        """
        self.review_total.labels(project=project, reviewer=reviewer, status=status).inc()
    
    def observe_review_duration(self, project: str, duration: float) -> None:
        """
        Observe review duration
        
        Args:
            project: Project identifier
            duration: Review duration in seconds
        """
        self.review_duration_seconds.labels(project=project).observe(duration)
    
    def set_active_reviewers(self, count: int, project: str = "all") -> None:
        """
        Set active reviewers count
        
        Args:
            count: Number of active reviewers
            project: Project identifier (or "all" for global)
        """
        self.active_reviewers.labels(project=project).set(count)
    
    def observe_review_score(self, project: str, score: float) -> None:
        """
        Observe review score
        
        Args:
            project: Project identifier
            score: Review score (0-10)
        """
        self.review_score.labels(project=project).observe(score)
    
    def set_users_total(self, count: int) -> None:
        """
        Set total users count
        
        Args:
            count: Total number of users
        """
        self.users_total.set(count)
    
    def set_users_active(self, count: int) -> None:
        """
        Set active users count
        
        Args:
            count: Number of active users
        """
        self.users_active.set(count)
    
    def increment_user_count(self) -> None:
        """Increment total users count"""
        self.users_total.inc()
    
    def decrement_user_count(self) -> None:
        """Decrement total users count"""
        self.users_total.dec()
    
    def set_reviewers_total(self, count: int) -> None:
        """
        Set total reviewers count
        
        Args:
            count: Total number of reviewers
        """
        self.reviewers_total.set(count)
    
    def set_reviewers_active(self, count: int) -> None:
        """
        Set active reviewers count
        
        Args:
            count: Number of active reviewers
        """
        self.reviewers_active.set(count)
    
    def increment_reviewer_count(self) -> None:
        """Increment total reviewers count"""
        self.reviewers_total.inc()
    
    def decrement_reviewer_count(self) -> None:
        """Decrement total reviewers count"""
        self.reviewers_total.dec()
    
    def set_projects_total(self, count: int) -> None:
        """
        Set total projects count
        
        Args:
            count: Total number of projects
        """
        self.projects_total.set(count)
    
    def set_projects_active(self, count: int) -> None:
        """
        Set active projects count
        
        Args:
            count: Number of active projects
        """
        self.projects_active.set(count)
    
    def increment_project_count(self) -> None:
        """Increment total projects count"""
        self.projects_total.inc()
    
    def decrement_project_count(self) -> None:
        """Decrement total projects count"""
        self.projects_total.dec()
    
    def set_repositories_total(self, count: int) -> None:
        """
        Set total repositories count
        
        Args:
            count: Total number of repositories
        """
        self.repositories_total.set(count)
    
    def increment_pull_request(self, project: str, status: str) -> None:
        """
        Increment pull request counter
        
        Args:
            project: Project identifier
            status: Pull request status
        """
        self.pull_requests_total.labels(project=project, status=status).inc()
    
    def set_pull_requests_open(self, count: int, project: str = "all") -> None:
        """
        Set open pull requests count
        
        Args:
            count: Number of open pull requests
            project: Project identifier (or "all" for global)
        """
        self.pull_requests_open.labels(project=project).set(count)
    
    def set_pull_requests_merged(self, count: int, project: str = "all") -> None:
        """
        Set merged pull requests count
        
        Args:
            count: Number of merged pull requests
            project: Project identifier (or "all" for global)
        """
        self.pull_requests_merged.labels(project=project).set(count)
    
    def increment_cache_hit(self, cache_type: str) -> None:
        """
        Increment cache hit counter
        
        Args:
            cache_type: Type of cache (e.g., "reviews", "projects", "users")
        """
        self.cache_hits_total.labels(cache_type=cache_type).inc()
    
    def increment_cache_miss(self, cache_type: str) -> None:
        """
        Increment cache miss counter
        
        Args:
            cache_type: Type of cache
        """
        self.cache_misses_total.labels(cache_type=cache_type).inc()
    
    def increment_cache_error(self, cache_type: str, error_type: str) -> None:
        """
        Increment cache error counter
        
        Args:
            cache_type: Type of cache
            error_type: Type of error
        """
        self.cache_errors_total.labels(cache_type=cache_type, error_type=error_type).inc()
    
    def set_db_connections_active(self, count: int) -> None:
        """
        Set active database connections count
        
        Args:
            count: Number of active connections
        """
        self.db_connections_active.set(count)
    
    def observe_db_query_duration(self, operation: str, duration: float) -> None:
        """
        Observe database query duration
        
        Args:
            operation: Type of database operation (e.g., "SELECT", "INSERT", "UPDATE", "DELETE")
            duration: Query duration in seconds
        """
        self.db_query_duration_seconds.labels(operation=operation).observe(duration)
    
    def increment_db_query(self, operation: str, table: str) -> None:
        """
        Increment database query counter
        
        Args:
            operation: Type of database operation
            table: Table name
        """
        self.db_queries_total.labels(operation=operation, table=table).inc()
    
    def set_cpu_usage(self, percent: float) -> None:
        """
        Set CPU usage percentage
        
        Args:
            percent: CPU usage percentage (0-100)
        """
        self.system_cpu_usage_percent.set(percent)
    
    def set_memory_usage(self, bytes_used: int) -> None:
        """
        Set memory usage
        
        Args:
            bytes_used: Memory used in bytes
        """
        self.system_memory_usage_bytes.set(bytes_used)
    
    def set_memory_available(self, bytes_available: int) -> None:
        """
        Set available memory
        
        Args:
            bytes_available: Available memory in bytes
        """
        self.system_memory_available_bytes.set(bytes_available)
    
    def set_disk_usage(self, path: str, bytes_used: int) -> None:
        """
        Set disk usage for a path
        
        Args:
            path: Filesystem path
            bytes_used: Disk used in bytes
        """
        self.system_disk_usage_bytes.labels(path=path).set(bytes_used)
    
    def set_disk_available(self, path: str, bytes_available: int) -> None:
        """
        Set available disk space for a path
        
        Args:
            path: Filesystem path
            bytes_available: Available disk space in bytes
        """
        self.system_disk_available_bytes.labels(path=path).set(bytes_available)
    
    def increment_error(self, error_type: str, endpoint: str) -> None:
        """
        Increment error counter
        
        Args:
            error_type: Type of error
            endpoint: API endpoint where error occurred
        """
        self.errors_total.labels(type=error_type, endpoint=endpoint).inc()
    
    def increment_rate_limit_error(self, endpoint: str) -> None:
        """
        Increment rate limit error counter
        
        Args:
            endpoint: API endpoint where rate limit was exceeded
        """
        self.errors_rate_limited_total.labels(endpoint=endpoint).inc()
    
    def increment_files_reviewed(self, project: str) -> None:
        """
        Increment files reviewed counter
        
        Args:
            project: Project identifier
        """
        self.files_reviewed_total.labels(project=project).inc()
    
    def increment_lines_changed(self, project: str, change_type: str) -> None:
        """
        Increment lines changed counter
        
        Args:
            project: Project identifier
            change_type: Type of change (e.g., "added", "deleted", "modified")
        """
        self.lines_changed_total.labels(project=project, change_type=change_type).inc()
    
    def observe_review_cycle_time(self, project: str, duration: float) -> None:
        """
        Observe review cycle time (PR creation to review)
        
        Args:
            project: Project identifier
            duration: Cycle time in seconds
        """
        self.review_cycle_time_seconds.labels(project=project).observe(duration)
    
    def observe_pr_merge_time(self, project: str, duration: float) -> None:
        """
        Observe PR merge time (PR creation to merge)
        
        Args:
            project: Project identifier
            duration: Time to merge in seconds
        """
        self.pr_merge_time_seconds.labels(project=project).observe(duration)
    
    def set_review_backlog(self, count: int, project: str = "all") -> None:
        """
        Set review backlog count
        
        Args:
            count: Number of PRs waiting for review
            project: Project identifier (or "all" for global)
        """
        self.review_backlog_count.labels(project=project).set(count)
    
    def set_reviewers_load(self, load: float, project: str = "all") -> None:
        """
        Set reviewer load (avg active PRs per reviewer)
        
        Args:
            load: Average load value
            project: Project identifier (or "all" for global)
        """
        self.reviewers_load.labels(project=project).set(load)
    
    def get_metrics(self) -> str:
        """
        Get metrics in Prometheus text format
        
        Returns:
            str: Metrics in Prometheus text format
        """
        return generate_latest(self.registry).decode('utf-8')
    
    def get_openmetrics(self) -> str:
        """
        Get metrics in OpenMetrics format
        
        Returns:
            str: Metrics in OpenMetrics format
        """
        return generate_latest_openmetrics(self.registry).decode('utf-8')
    
    def metrics_response(self, format: str = "prometheus") -> Response:
        """
        Get metrics as FastAPI Response
        
        Args:
            format: Output format ("prometheus" or "openmetrics")
            
        Returns:
            Response: FastAPI response with metrics
        """
        if format == "openmetrics":
            metrics = self.get_openmetrics()
            content_type = "application/openmetrics-text; version=0.0.1; charset=utf-8"
        else:
            metrics = self.get_metrics()
            content_type = CONTENT_TYPE_LATEST
        
        return Response(content=metrics, media_type=content_type)
    
    def startup(self) -> None:
        """Initialize metrics on application startup"""
        logger.info("Starting metrics collection")
        # Initialize counters to 0 if needed
        self.users_total.set(0)
        self.reviewers_total.set(0)
        self.projects_total.set(0)
        self.repositories_total.set(0)
    
    def shutdown(self) -> None:
        """Cleanup metrics on application shutdown"""
        logger.info("Stopping metrics collection")


# Timing context manager for measuring operation duration
class OperationTimer:
    """Context manager for timing operations"""
    
    def __init__(self, metrics: MetricsCollector, operation_type: str, labels: Dict[str, str]):
        """
        Initialize operation timer
        
        Args:
            metrics: MetricsCollector instance
            operation_type: Type of operation (e.g., "http_request", "db_query")
            labels: Labels to apply to the metric
        """
        self.metrics = metrics
        self.operation_type = operation_type
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        """Start timing"""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and record duration"""
        if self.start_time:
            duration = time.time() - self.start_time
            
            if self.operation_type == "http_request":
                self.metrics.observe_http_request_duration(
                    method=self.labels.get("method", "unknown"),
                    endpoint=self.labels.get("endpoint", "unknown"),
                    duration=duration
                )
            elif self.operation_type == "db_query":
                self.metrics.observe_db_query_duration(
                    operation=self.labels.get("operation", "unknown"),
                    duration=duration
                )
            elif self.operation_type == "review":
                self.metrics.observe_review_duration(
                    project=self.labels.get("project", "unknown"),
                    duration=duration
                )
            elif self.operation_type == "review_cycle":
                self.metrics.observe_review_cycle_time(
                    project=self.labels.get("project", "unknown"),
                    duration=duration
                )
            elif self.operation_type == "pr_merge":
                self.metrics.observe_pr_merge_time(
                    project=self.labels.get("project", "unknown"),
                    duration=duration
                )


def measure_operation(
    metrics: MetricsCollector,
    operation_type: str,
    labels: Dict[str, str]
):
    """
    Decorator for measuring operation duration
    
    Args:
        metrics: MetricsCollector instance
        operation_type: Type of operation
        labels: Labels to apply to the metric
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with OperationTimer(metrics, operation_type, labels):
                return await func(*args, **kwargs)
        return async_wrapper
    return decorator


# Global metrics collector instance
metrics = MetricsCollector()