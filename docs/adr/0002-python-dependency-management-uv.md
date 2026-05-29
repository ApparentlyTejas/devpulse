# ADR-0002: Use uv for Python dependency management

- **Status:** Accepted
- **Date:** 2026-05-19

## Context

We need a Python dependency manager for the backend that gives us:

- Reproducible installs across dev, CI, and production images.
- A single source of truth for project metadata (`pyproject.toml`).
- Fast install times in CI.
- Lockfile committed to git.

## Decision

We use **uv** (https://github.com/astral-sh/uv), the Rust-based Python
package manager from Astral. The project is described by `pyproject.toml`
and pinned by `uv.lock`. Both are committed.

Dev tooling is installed via the `dev` optional-dependency group. Production
images install with `uv sync --no-dev` to keep the runtime closure minimal.

## Alternatives considered

- **Poetry.** Mature, ubiquitous, fine. Slower than uv (often 10×+) and
  the lockfile format is less ergonomic. Still a reasonable choice; if a
  future contributor strongly prefers it, this ADR is reversible.
- **pip + pip-tools.** Explicit and minimal but requires more manual
  ceremony (compile, sync) and lacks a clean way to manage the interpreter.
- **PDM.** Capable. Smaller community than Poetry, similar perf to uv but
  lower velocity.

## Consequences

- Builds and CI are noticeably faster.
- The Docker build uses the official `ghcr.io/astral-sh/uv` image to copy
  the binary at a pinned version, avoiding curl-pipe-shell installs.
- Contributors must install uv locally; we document this in `README.md`.
