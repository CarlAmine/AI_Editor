# Contributing to AI Editor

Thank you for your interest in contributing. This document covers how to set up a development environment, coding conventions, and how to submit changes.

---

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Shotstack Stage API key (free)
- Groq API key

### Backend

```bash
git clone https://github.com/CarlAmine/AI_Editor.git
cd AI_Editor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in your keys
python app.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
pytest tests/ -v
```

---

## Code Conventions

- **Python**: follow PEP 8; use type hints on public functions.
- **FastAPI routes**: keep route handlers thin — delegate logic to `ai_editor/` or `pipeline/` modules.
- **Pipeline stages**: new stages belong in `pipeline/runner.py` following the existing stage pattern.
- **Tests**: add a `tests/test_<module>.py` for any new module with non-trivial logic.
- **Commits**: use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.

---

## Submitting Changes

1. Fork the repository and create a feature branch: `git checkout -b feat/my-feature`
2. Make your changes and write or update tests.
3. Run `pytest tests/ -v` and confirm all tests pass.
4. Open a Pull Request against `main` with a clear description of the change and why.

---

## Reporting Issues

Use the [GitHub Issues](https://github.com/CarlAmine/AI_Editor/issues) page.
For bugs, use the **Bug Report** template. For ideas, use **Feature Request**.

---

## Questions

Open a [Discussion](https://github.com/CarlAmine/AI_Editor/discussions) or comment on a relevant issue.
