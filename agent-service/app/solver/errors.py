class SolverError(Exception):
    """Base exception for solver engine."""
    pass


class SolverValidationError(SolverError):
    """Raised when calculation input fails validation."""
    pass


class RevisionConflictError(SolverError):
    """Raised when revision changes and retries are exhausted."""
    pass


class SolverAPIError(SolverError):
    """Raised when backend API returns an unexpected error."""
    pass
