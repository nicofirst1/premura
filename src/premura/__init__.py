"""premura — personal health data warehouse."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("premura")
except PackageNotFoundError:  # running from an uninstalled source tree
    __version__ = "0.0.0+unknown"
