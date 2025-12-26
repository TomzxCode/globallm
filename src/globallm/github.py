"""GitHub client utilities."""

from github import Github

from globallm.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_PER_PAGE = 100


def create_github_client(token: str | None = None, **kwargs) -> Github:
    """Create a GitHub client with default settings.

    Args:
        token: Optional GitHub API token
        **kwargs: Additional settings to pass to Github()

    Returns:
        Github client instance with per_page=100 by default
    """
    settings = {"per_page": _DEFAULT_PER_PAGE, **kwargs}
    client = Github(token, **settings) if token else Github(**settings)

    if token:
        logger.debug("github_client_created", authenticated=True)
    else:
        logger.debug("github_client_created", authenticated=False)

    return client
