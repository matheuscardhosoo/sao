# Underworld Project Standards

## Technical Stack

- Language: Python 3.10+
- Web Framework: FastAPI (High performance, auto-docs)
- Validation: Pydantic v2
- Orchestration: Docker (optional) / UV (dependency manager)

## Coding Principles

1. **Type Safety**: Use Python Type Hints everywhere.
2. **Domain Separation**: Game logic (src/engine) must be independent of API logic (src/api).
3. **Telemetry First**: Every significant agent action must be logged via the analytics module.
4. **Resilience**: Use Try-Except blocks for LLM API calls to prevent agent "brain death" on network errors.

## Code Style

- **Python**: Use type hints for all function signatures and public APIs
- **Formatting**: Line length 100; use Ruff for linting (E, F, I, UP)
- **Imports**: Absolute imports; group stdlib, third-party, local

## Structure

- `src/engine` - World state, simulation logic, models
- `src/api` - FastAPI application, endpoints
- `src/agents` - Agent implementations
- `src/utils` - Shared utilities, logging
- `configs` - Configuration files
- `logs` - Runtime logs, telemetry

## Conventions

- Use Pydantic for request/response schemas
- Use Loguru for structured logging
- Load secrets/config via python-dotenv
- Keep modules decoupled; avoid circular imports

## Documentation

- Every new function must have a brief docstring explaining the 'vibe' and the technical purpose.