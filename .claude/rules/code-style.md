# Code Style Guidelines

## General Principles

- Keep code simple and readable
- Prefer explicit over implicit
- Follow existing patterns in the codebase

## Bash Scripts (AAXtoMP3)

- Use `#!/usr/bin/env bash` shebang
- Quote all variable expansions: `"$variable"` not `$variable`
- Use `[[ ]]` for conditionals instead of `[ ]`
- Prefer `$(command)` over backticks for command substitution
- Use meaningful variable names in UPPER_CASE for globals, lower_case for locals
- Add comments for non-obvious logic

## Python (API - FastAPI)

- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Use async/await for I/O-bound operations
- Keep functions focused and small
- Use Pydantic models for request/response validation

## TypeScript/React (Web App)

- Use functional components with hooks
- Prefer named exports over default exports
- Use TypeScript strict mode
- Keep components small and focused
- Co-locate related files (component, styles, tests)
- Use descriptive variable and function names

## Formatting

- Use project-specific formatters (Prettier for TS/JS, Black for Python)
- Run formatters before committing
- Consistent indentation: 2 spaces for JS/TS, 4 spaces for Python
