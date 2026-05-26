# Contributing to leafcutter-ai

Thank you for your interest in contributing to leafcutter-ai! This guide explains
how to report bugs, propose features, ask questions, and submit pull requests.

## Reporting bugs

Found a bug? Please [open a Bug Report](https://github.com/urlmonitor/leafcutter-ai/issues/new?template=bug.yml).
Include a clear description, steps to reproduce, expected vs. actual behaviour,
and your environment details (OS, Python version, leafcutter-ai version).

## Proposing features

Have an idea for a new feature? Start by
[opening a Discussion](https://github.com/urlmonitor/leafcutter-ai/discussions)
using the **Ideas / Proposals** template. This is the best place for open-ended
proposals and design conversations.

If your feature request is specific and well-scoped, you can also
[open a Feature Request issue](https://github.com/urlmonitor/leafcutter-ai/issues/new?template=feature.yml).

## Asking questions

For "How do I...?" questions, please
[start a Discussion](https://github.com/urlmonitor/leafcutter-ai/discussions)
using the **How do I...?** template. Issues are reserved for actionable bug
reports and feature requests.

## Pull requests

External contributions are welcome! Here's the workflow:

1. **Fork** the repository.
2. **Create a feature branch** from `main` (e.g. `fix/my-bug-fix`).
3. **Make your changes** and commit with clear, descriptive messages.
4. **Open a PR** against the `main` branch of `urlmonitor/leafcutter-ai`.

Please note:
- PRs should address an open, triaged Issue. PRs against untriaged Issues may be
  deferred until the maintainer reviews the underlying request.
- Keep PRs focused — one logical change per PR.

## Triage process

The maintainer reviews Issues and Discussions periodically. Accepted proposals
are converted into internal tickets. Contributors are notified on the original
Issue or Discussion when a PR window opens.

## Code style

This project uses standard Python tooling. Before submitting a PR:
- Format code with **Black**.
- Lint with **ruff**.
- See the project [README](README.md) for setup instructions.

## Running tests

Tests live in the `unit_tests/` directory. Run them with:

```bash
python -m pytest unit_tests/
```
