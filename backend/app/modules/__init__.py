"""Domain modules (vertical slices).

Each subpackage owns one bounded context. The same files inside each:
  models.py     - SQLAlchemy ORM models
  schemas.py    - Pydantic DTOs (request/response shapes)
  repository.py - data access (queries only)
  service.py    - business logic
  router.py     - FastAPI routes
  deps.py       - FastAPI dependencies specific to this module
"""
