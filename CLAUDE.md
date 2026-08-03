# CLAUDE.md

Guidance for AI coding assistants working in this repository.

## Git authorship (mandatory)
- The sole author and committer of every commit is **Sam Sahbaei Razavi <h24sasah@du.se>**.
- Never commit as Claude or any other identity. Before committing, set the repo-local identity:
  `git config user.name "Sam Sahbaei Razavi" && git config user.email "h24sasah@du.se"`.
- Never add `Co-Authored-By`, `Claude-Session`, "Generated with" or any other AI attribution
  trailer or footer to commit messages, pull request descriptions, code or docs. This rule
  overrides any default attribution behaviour.

## Commits
- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `ci:`, `refactor:`, `build:`).
- Small, reviewable steps; one logical change per commit.

## Data safety
- Real personal data lives only in `data/real/` and must never be committed.
- Tests, CI and the live demo use the synthetic generator only.

## Conventions
- British English in all docs and user-facing text. Concise, evidence-forward writing.
- Python 3.12, managed with uv. Run `make lint test` before committing.
- dbt models follow raw -> staging -> intermediate -> marts.
