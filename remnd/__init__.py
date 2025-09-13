from importlib.metadata import version, PackageNotFoundError

__all__ = ["__version__"]

try:
    __version__ = version("remnd")
except PackageNotFoundError:  # dev/editable installs
    __version__ = "0.0.0"

