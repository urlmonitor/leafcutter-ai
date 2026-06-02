# Testing Conventions

This document describes the testing conventions for this project.

## Running Tests

Consult the project's CLAUDE.md or pyproject.toml for test commands.

## Directory Structure

Tests are organised by module. Each test file should follow the
`test_*.py` naming convention.

## Guidelines

- Keep tests fast (< 5 seconds per test)
- Use descriptive test names that explain the expected behaviour
- Prefer integration tests over mocks for database-dependent code
