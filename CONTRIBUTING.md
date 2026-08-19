# Contributing to OS-Manager

Thank you for your interest in contributing to `os-manager`. This project welcomes contributions from everyone.

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Workflow

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create a descriptive feature branch:
   ```bash
   git checkout -b feat/my-new-feature
   ```
4. Follow the Test-Driven Development (TDD) discipline:
   - Write failing unit tests first.
   - Implement the minimal necessary changes.
   - Verify that all tests pass.
5. Ensure your scripts pass static analysis:
   ```bash
   shellcheck scripts/**/*.sh tests/**/*.sh
   python3 -m py_compile scripts/*.py os_manager/**/*.py
   ```
6. Verify that the master harness passes:
   ```bash
   ./tests/test_harness.sh
   ```
7. Commit your changes following Conventional Commits format (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`).
8. Open a Pull Request on GitHub.

## Testing and Quality Assurance

Run the test harness before submitting a pull request:

```bash
./tests/test_harness.sh
```

Ensure all unit tests and static analysis gates pass.

## Coding and Style Standards

- Maintain strict `set -euo pipefail` on all shell scripts.
- Use POSIX LF line endings.
- Do not introduce external runtime dependencies for core CLI utilities.
- Follow the writing rules defined in `agent-style v0.4.2` for all markdown documentation.
