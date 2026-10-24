# Implementation Notes

## Problems found

- **Missing valid windows:** Code review found an exclusive upper bound in the window search. Included the last legal start, covering 16:45–17:00, exact end bounds, and full-day meetings.
- **Incorrect durations:** A 45-minute request was silently truncated to 30 minutes by integer division. Durations now require positive integer multiples of the configured interval and cannot exceed the working day.
- **Explicit constraints overwritten:** Verification found “afternoon after 16:00” reset the lower bound to noon. Day-part bounds now intersect explicit bounds; added lower/upper-bound and contradiction regressions.
- **Attendees omitted by the model:** A scripted call dropped Sam and offered times when he was busy. Added a deterministic pre-tool check of user attendee clauses and known directory mentions, independent of model arguments. Time-only follow-ups retain the last verified group; explicit new lists replace it. Mismatches fail before a calendar lookup. Unsupported additive/negative edits request a complete list.
- **Invalid search bounds:** Reproduction showed starts before `earliest` and meetings after 17:00. Bounds now validate against working hours and round inward to the grid.
- **Invented employees:** Unknown IDs looked like empty calendars. Both calendar tools now resolve names against the directory using normalized exact matches and conservative fuzzy similarity, reject low-confidence or ambiguous names, and reject empty attendee lists.
- **Unvalidated data:** Added strict clock/date checks, availability lengths, busy-block ordering, unique employee IDs, and fixture ownership validation. Missing calendar entries for known employees mean no recorded busy blocks.
- **Crashes and infinite loops:** Malformed JSON, unexpected action shapes, unknown tools, bad arguments, and model failures were unhandled. Added explicit error responses and a per-request call budget. Optional HTTP calls have a timeout.
- **Unverified final answers:** The model could invent times even after a correct tool result. User-visible answers now render current-turn tool data; arbitrary model final text is not published. A turn without verified data requests scheduling details.
- **Tests masked defects:** The afternoon expectation omitted a valid final window; corrected it and added quarter-hour starts. Updated conversion/overlap tests for the new grid, replaced the short-calendar prefix assertion with a full-day assertion plus rejection coverage, and changed final-answer tests to assert verified rendering. Added regression coverage across all layers.

## My additions

- **Main addition — interactive terminal:** Employees can start `--interactive` and refine availability through follow-up questions about different times, dates, durations, or people without restarting. It works offline with `InteractiveFakeModel`, retains the last ten turns, and supports `/new` and `/quit`. Real-model access is optional through `--real-model`.
This was chosen mainly because it seems like a must have as bookins is an interactive process rather than having to send commands again and again.
- **Minor improvement — finer scheduling:** Fifteen-minute intervals support exact 15/45-minute meetings. Prompts derive the interval and working hours from `slots.py` to stay consistent with calculations.
- **Minor improvement — typo-tolerant names:** Conservative fuzzy matching accepts clear misspellings while rejecting uncertain matches and displaying resolved employee names for review.

## How AI tools were used

- Asked AI to explain architecture/tests, create `AGENTS.md` (init), review gaps and tests.
- Corrected the suggestion to hardcode “15 minutes” in the prompt: importing scheduling settings keeps instructions consistent with the core.
- Corrected AI's decision to require a real model for interactive mode: follow-up conversations must also work offline with a FakeModel implementation, consistent with the assignment's no-API evaluation. Replaced that restriction with a deterministic interactive fake while preserving scripted FakeModel tests.
- Corrected AI's exact-only name matching: employees may mistype names. Added normalized fuzzy matching with explicit confidence and separation thresholds, rejecting ambiguous inputs instead of guessing and displaying the matched identity for review. Ai asked to change the 30 min window in prompt to 15 mins, I corrected it to use dynamic values from time slots.py instead of hardcoding it.
- Verified all the suggested changes, built a plan to do these in the order of Part A to solve specific tasks in each run. Built goal for additions and let agent handle the implementation.
- Removed identical demo answers from the defect list: scripted behavior is expected and is now clearly labeled. Removed booking from planned features because `task.md` explicitly excludes calendar writes.

## Next Steps:
- **Ask targted clarification questions:** Currently, some incomplete requests receive a general instruction to provide scheduling details. A better response would identify exactly what is missing: “How long should the meeting be?” or “Which Sam did you mean?” Keep a pending request so the user can answer “45 minutes” without repeating the attendees and date. For uncertain name matches, offer directory candidates and require a selection.
- **Add lightweight observability:** Record request duration, model-call count, timeout count, validation failures, ambiguous-name failures, and worker exits. These measurements would reveal whether users struggle with the supported grammar or whether requests frequently reach execution limits. Use error categories and timings rather than logging full prompts or calendar contents by default.

## Validation and assumptions
- Tests use `FakeModel`, including malformed responses, repeated calls, session isolation, changed people/times, and CLI interactions. Offline parser, typo, ambiguity, reset, and CLI tests are also covered. No real-model service was used.
- Interpretation remains dependent on the selected model or limited offline grammar: explicit attendee clauses and known name mentions are checked independently against tool arguments, including inherited groups. This is not a general language parser: implicit references and names outside supported clauses still need structured request confirmation before claiming unrestricted interpretation guarantees.
- Requests now run in disposable processes under a shared wall-clock deadline, covering model calls, tools, parsing, and validation. Timeout cleanup terminates then kills a stubborn worker; partial session/model state is discarded. The separate call budget remains in place.



