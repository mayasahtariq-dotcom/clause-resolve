"""ASGI entry point: uvicorn clauselens.main:app"""

from clauselens.api.app import create_app

app = create_app()
