# Testing Conventions

## API Testing (Python/FastAPI)

### Unit Tests
- Located in `apps/api/tests/unit/`
- Test individual functions and classes in isolation
- Mock external dependencies (database, file system, external APIs)
- Run with: `pytest apps/api/tests/unit/`

### Integration Tests
- Located in `apps/api/tests/integration/`
- Test API endpoints and service interactions
- Use test database fixtures
- Run with: `pytest apps/api/tests/integration/`

### Running All API Tests
```bash
# From project root
docker exec -it audible-api-dev pytest

# Or locally with virtual environment
cd apps/api && pytest
```

## Web Testing (TypeScript/React)

### Unit Tests
- Located in `apps/web/tests/unit/`
- Test components, hooks, and utilities
- Use React Testing Library for component tests
- Run with: `npm test` in apps/web directory

### Test File Naming
- Test files should be named `*.test.ts` or `*.test.tsx`
- Co-locate test files with source or in `tests/` directory

## Bash Script Testing (AAXtoMP3)

No formal test suite exists. Manual validation:
- Use `-V` flag to validate AAX files without converting
- Use debug mode (`-d`) for verbose output
- Test with sample files before major changes

## Test Guidelines

- Write tests for new features and bug fixes
- Aim for meaningful coverage, not 100% coverage
- Test edge cases and error conditions
- Keep tests independent and idempotent
- Use descriptive test names that explain the scenario
