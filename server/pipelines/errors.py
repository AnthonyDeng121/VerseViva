class PipelineOutputError(ValueError):
    """Raised when a model artifact cannot be converted into project data."""


class ModelExecutionError(RuntimeError):
    """Raised when a model process cannot start or exits unsuccessfully."""


class MissingModelArtifactError(PipelineOutputError):
    """Raised when a successful model process did not create an expected artifact."""
