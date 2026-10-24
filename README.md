# Northwind Scheduling Assistant (Python)

A small agentic assistant that helps employees find meeting times. A user
types a request in plain English ("find 45 minutes with Priya and Sam next
Tuesday afternoon"); a language model turns it into tool calls; the tools
look up calendars and compute when everyone is free.

This codebase was written quickly by an AI coding agent. Treat it the way you
would treat code you inherited from a teammate: it runs, and the tests pass,
and has since been reviewed for scheduling correctness and model failure handling.

## Layout

```
data/                 Sample directory (people.json) and calendars (calendars.json)
scheduler/
  slots.py            Working-day slot model and free-window search
  tools.py            Tools the agent can call
  agent.py            The tool-calling loop
  prompts.py          System prompt construction
  model.py            Model interface + FakeModel for tests
  real_model.py       Optional adapter for OpenAI-compatible endpoints
  store.py            Loads the JSON data
main.py               CLI entry point
tests/                pytest suite
```

## Running

Requires Python 3.10+.

```bash
pip install pytest
python -m pytest
python main.py "Find an hour for Priya and Sam on Tuesday afternoon"
```

Sample calendar data covers Monday 2 November to Wednesday 4 November 2026.
"Today" is Monday 2 November 2026.

## Models

`FakeModel` returns scripted responses, so you can test the agent without any
API access. Script responses are raw strings, which lets you simulate
malformed or unexpected model output as well as well-formed JSON. The helpers
`tool_call(...)` and `final(...)` build well-formed responses.

You do not need a real model for this assignment, and using one earns no extra
credit. If you want to try one anyway, `real_model.py` works with any
OpenAI-compatible endpoint, including a local server such as Ollama:

```bash
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=llama3.1
python main.py "Find 30 minutes with Mei and Luis on Tuesday"
```

## Scheduling and follow-up questions

Availability uses 15-minute increments, including exact 45-minute meetings.
Working hours are 09:00–17:00. Durations must be positive multiples of the
configured interval and fit within one working day. Bounds round inward to
the grid. Unknown employees and invalid arguments produce an explicit error.
A missing date for a known employee means no recorded busy blocks; this does
not establish that calendar data exists outside the sample period.

The default CLI is a **scripted demo**, always checking Priya and Sam on
November 3 regardless of input. Interactive sessions use an offline `InteractiveFakeModel` by default; no
API, configuration, or model service is required:

```bash
python main.py --interactive
# Find 45 minutes with Priyaa and Sam on Tuesday afternoon
# What about after 16:00?
# Now check Mei and Luis before noon
```

Use `/new` to clear context and `/quit` to exit; EOF also exits. Each session
keeps the last ten turns. Programmatic callers can reuse one
`SchedulingAgent` and call `run()` repeatedly, or call `reset()` to start over.
`InteractiveFakeModel` subclasses `FakeModel` and derives tool calls from a
small deterministic grammar rather than replaying fixed answers. It supports
names after `with`, `for`, `check`, or `about`, plus subject-first lists such as
`Sam and Mei need 45 minutes`; numeric minutes or hours (including `1.5 hours`);
ISO dates, weekdays, today/tomorrow; morning/afternoon; and `after`/`before`
HH:MM or noon. Numeric values are parsed in full; negative, non-grid, and
conflicting durations are rejected. All bounds in one request are intersected.
Omitted constraints carry forward; a new time bound replaces
previous bounds. Start a new session with a complete request. This is a local
demo parser, not general natural-language understanding; use the documented
forms. Exact `at` requests are unsupported and request clarification.
Use `--interactive --real-model` to explicitly opt into a configured endpoint.
The original scripted `FakeModel` remains available unchanged for test scripts.

Name resolution normalizes case, accents, spacing, and punctuation. Exact IDs
and full names take priority. Otherwise `SequenceMatcher` compares IDs, full
names, and (for one-word inputs) name components. The best candidate must score
at least 0.80 and lead the runner-up by at least 0.10. Ambiguous/low-confidence
inputs are rejected; results display the resolved directory names. Thresholds
are named constants in `scheduler/tools.py`. Similarity is a heuristic, so users
should review the displayed identities.

The agent allows at most eight model calls per request and enforces a shared
30-second deadline in a disposable worker process. It handles malformed responses
and tool errors; the optional adapter also uses a 30-second HTTP timeout. It renders current-turn tool results itself instead of publishing
unverified model final text. A final response without tool results asks for
attendees, date, and duration. Booking and calendar writes are unsupported.

The selected model or offline grammar interprets requests and follow-up constraints. Code
checks recognized attendee lists, durations, and time bounds against tool arguments
before offering times. Unrecognized language and implicit references still require
clarification; the demo does not implement unrestricted language understanding. FakeModel tests verify
context delivery and deterministic behavior, not a real model's comprehension.

## Request execution limits

Each request has at most eight model calls and a shared 30-second wall-clock
budget. Set `SchedulingAgent(..., timeout_seconds=5)` to change the budget.
The whole request runs in a disposable worker process. A blocked model or tool
is terminated (then killed if necessary); the caller receives a timeout message.
Partial results and session changes are discarded. Cleanup adds at most two
0.1-second waits under normal process scheduling, plus startup/result overhead.

FakeModel script consumption and call snapshots are synchronized back after
completion. Other custom models execute in the worker; their in-memory mutations
are isolated. POSIX uses fork, intended for this single-threaded CLI; other
platforms use spawn and require a picklable model and a guarded entry point
(`if __name__ == "__main__":`). Snapshot results larger than 8 MiB fail safely.
