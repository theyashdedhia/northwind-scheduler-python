# Implementation Notes

## Problems found

- The free-window search excluded its final legal start. Included that boundary and added full-day and exact-end tests.
- Durations were truncated and search bounds could offer starts before the requested time or after work. Validate durations, round bounds inward, and enumerate every legal window on the configured grid.
- Day-part parsing overwrote explicit bounds: “afternoon after 16:00” returned afternoon times before 16:00. Intersect these constraints and reject contradictions.
- A model could omit Sam from a Priya-and-Sam request and offer times when Sam was busy. Independently check explicit attendee clauses and known name mentions before tool execution. Time-only follow-ups retain the verified group; explicit replacements use the new group. Reject mismatches and unsupported additive/negative edits.
- Model final text could invent times. Render verified current-turn tool results instead.

## My additions

- Fifteen-minute scheduling supports exact 45-minute meetings. Prompts derive the interval and working hours from the core.
- The conversation/model support included here is required to check inherited attendee groups and regression-test explicit-bound parsing offline. CLI entry-point changes are separate.
- Directory resolution uses normalized exact identities and conservative fuzzy matching (0.80 similarity, 0.10 minimum lead); ambiguous names require clarification.

## How AI tools were used

- AI reviewed the architecture and implemented fixes and regression tests.
- Corrected AI's hardcoded prompt interval to derive it from slots.py.
- Corrected AI's exact-only identity matching and real-model-only interactive assumption; offline FakeModel behavior is covered by tests.

## Validation and assumptions

- Corrected the original afternoon expectation, which encoded a missing final window, and updated slot tests for the finer grid and strict full-day lengths.
- Verified availability against an independent interval-overlap oracle: 6,048 sample-calendar combinations and 1,000 generated calendars with off-grid/overlapping busy blocks.
- Regression tests cover model omission/addition of attendees, typo resolution, inherited/replaced groups, explicit day-part bounds, and conflicting bounds.
- Missing calendar entries for known employees mean no recorded busy blocks. Completeness is defined over the configured grid and supported durations.
- Attendee checks handle explicit lists and known mentions, not unrestricted natural language or implicit references. Structured confirmation remains necessary for unrestricted interpretation guarantees. Booking remains outside scope.

## Part A.2 verification and fixes

- Verification found unknown names could bypass validation when the model returned only final text or looked up another person's busy times. Resolve request attendees before the first model call; an unknown or ambiguous name now produces an explicit directory error regardless of model behavior.
- The attendee parser previously inspected only its first clause. It now reads every supported clause, including “with Sam on Tuesday and with Ghost”, adjacent repeated clauses, and separate sentences.
- Added regressions for final-only, directory, busy-lookup, and incomplete scheduling actions; unknown follow-ups; and the offline fake path. These assert that rejected requests make no model calls and never reuse a previous availability answer.
- Updated the existing omission test to expect zero model calls for an unknown user name, since rejection now happens earlier; valid-name mismatches still require one model call.
- Scope remains explicit attendee clauses and known directory mentions, not unrestricted natural-language name recognition. Similarity resolution still targets directory entries only.

## Part A.3 duplicate-key handling

- Verification found Python's default JSON parser silently kept the final value of a repeated key, allowing conflicting durations to produce a wrong answer.
- Added an object-pairs hook that rejects duplicate keys at every object depth before tool execution. The existing controlled-error path reports the offending key.
- Regressions cover action keys, nested arguments, objects in arrays, identical repeated values, Unicode-escaped equivalent keys, and rejection after a successful lookup without publishing stale availability.
