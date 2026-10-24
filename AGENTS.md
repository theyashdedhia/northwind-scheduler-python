# Repository Guidelines

## Project Structure & Module Organization

- `main.py` is the CLI entry point and selects the scripted demo or an optional real model.
- `scheduler/agent.py` orchestrates model responses and tool execution; `prompts.py` builds the system prompt.
- `scheduler/tools.py` exposes directory and calendar operations. Keep availability calculations in the deterministic core, `scheduler/slots.py`.
- `scheduler/model.py` defines the model interface and `FakeModel`; `real_model.py` contains the optional HTTP adapter.
- `scheduler/store.py` loads sample fixtures from `data/people.json` and `data/calendars.json`.
- `tests/` mirrors the core, tools, and agent layers. `NOTES.md` records findings, decisions, AI assistance, and follow-up work.

## Build, Test, and Development Commands

Requires Python 3.10+. No separate build step is needed.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "pytest>=8"
python -m pytest
python -m pytest tests/test_slots.py -q
python main.py "Find an hour for Priya and Sam on Tuesday afternoon"
```

The test commands run the complete suite or one module. The default CLI runs a fixed scripted demo. Use `python main.py --interactive` for offline follow-ups with `InteractiveFakeModel`; `/new` clears context and `/quit` exits. Its documented grammar supports named attendees, dates, durations, and time bounds. A real model is optional.

## Coding Style & Naming Conventions

Use four-space indentation, PEP 8 conventions, `snake_case` functions and variables, `PascalCase` classes, and uppercase constants. Follow existing type hints and short docstrings. Keep model orchestration separate from scheduling logic, and return JSON-serializable tool results. No formatter or linter is currently configured.

## Testing Guidelines

Use pytest with files named `tests/test_*.py` and functions named `test_*`. Use `FakeModel`, `tool_call()`, and `final()` for agent tests; API access is unnecessary. Add regression tests for changed behavior, especially time boundaries, unknown attendees, malformed responses, invalid arguments, and termination. No numerical coverage threshold is configured. Run the full suite before submitting; explain any changes to existing expectations in `NOTES.md`.

## Commit & Pull Request Guidelines

The limited history uses short descriptive subjects, such as `Added notes.md to document work`; no strict commit format is established. Make focused commits as work progresses. PR descriptions should explain the problem, resulting behavior, tests run, and assumptions or limitations. Link relevant issues when available. Update `README.md` when run instructions change.

## Configuration & Scope

Keep credentials out of source control. Optional model configuration uses `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`. Sample dates cover November 2–4, 2026, and the default simulated “today” is November 2. Keep work focused on finding availability; calendar writes, time zones, and recurring meetings are outside the assignment scope.
