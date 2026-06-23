"""PyInstaller entry point for the bundled backend.

Freezing this produces a standalone backend executable so the packaged app
needs no system Python. It just runs the same Flask API + sync scheduler as
`python -m backend.api`.
"""
from backend.api import main

if __name__ == "__main__":
    main()
