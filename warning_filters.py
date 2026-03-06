import warnings


def suppress_pkg_resources_deprecation_warning():
    """Hide python-can's pkg_resources deprecation warning from startup logs."""
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
        module="can.io.logger",
    )


# Apply immediately on import so simply importing this module is enough.
suppress_pkg_resources_deprecation_warning()
