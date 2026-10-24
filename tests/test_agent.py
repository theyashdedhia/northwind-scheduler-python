import json

import pytest

from scheduler.agent import SchedulingAgent
from scheduler.model import FakeModel, final, tool_call
from scheduler.prompts import build_system_prompt
from scheduler.store import Store
from scheduler import slots


def schedule(**overrides):
    args = dict(attendees=["priya", "sam"], date="2026-11-03",
                duration_minutes=60, earliest="13:00", latest="14:00")
    args.update(overrides)
    return tool_call("find_free_slots", **args)


def test_agent_renders_verified_result_not_model_claim():
    model = FakeModel([schedule(), final("Ghost is free at 03:00.")])
    answer = SchedulingAgent(model, Store.load()).run("Find an hour for Priya and Sam")
    assert "Priya Raman, Sam Okafor" in answer
    assert "13:00–14:00" in answer
    assert "Ghost" not in answer and "03:00" not in answer
    result = model.calls[1][-1]
    assert result["role"] == "tool"
    assert json.loads(result["content"]) == [{"start": "13:00", "end": "14:00"}]


def test_unverified_final_cannot_offer_meetings():
    agent = SchedulingAgent(FakeModel([final("Ghost can meet at 03:00")]), Store.load())
    assert "no availability has been verified" in agent.run("hello")


@pytest.mark.parametrize("raw", [
    "not json", "[]", "null", '{"final": 42}', '{"final": ""}',
    '{"tool":"missing","args":{}}', '{"tool":[],"args":{}}',
    '{"tool":"list_people","args":[]}', '{"tool":"list_people"}',
    '{"final":"ok","tool":"list_people","args":{}}',
    tool_call("get_busy_times", person="sam"),
    tool_call("list_people", unexpected=True),
    schedule(attendees=["ghost"]), schedule(duration_minutes=0),
])
def test_bad_model_output_and_arguments_fail_gracefully(raw):
    answer = SchedulingAgent(FakeModel([raw]), Store.load()).run("Find a time")
    assert answer.startswith("Unable to complete the request:")


def test_repeated_calls_stop_at_budget():
    model = FakeModel([tool_call("list_people")], loop_last=True)
    answer = SchedulingAgent(model, Store.load(), max_steps=3).run("Find a time")
    assert "limit" in answer
    assert len(model.calls) == 3


def test_model_failure_is_handled():
    assert "unavailable" in SchedulingAgent(FakeModel([]), Store.load()).run("hi")


def test_follow_ups_preserve_context_and_recheck_changed_people_and_times():
    model = FakeModel([
        schedule(), final("done"),
        schedule(earliest="16:00", latest="17:00"), final("done"),
        schedule(attendees=["mei", "luis"], earliest="09:00", latest="10:00"), final("done"),
    ])
    agent = SchedulingAgent(model, Store.load())
    first = "Find an hour for Priya and Sam on Tuesday at 13:00"
    assert "13:00–14:00" in agent.run(first)
    assert "16:00–17:00" in agent.run("What about after 16:00?")
    answer = agent.run("Now check Mei and Luis before 10:00")
    assert "Mei Tanaka, Luis Moreno" in answer and "09:00–10:00" in answer
    assert any(m["content"] == first for m in model.calls[2])
    assert len([m for m in model.calls[4] if m["role"] == "user"]) == 3
    # This tests history plumbing and new calculations, not real-model understanding.


def test_new_turn_cannot_reuse_old_availability_and_reset_clears_context():
    model = FakeModel([schedule(), final("done"), final("Use the old result"), final("done")])
    agent = SchedulingAgent(model, Store.load())
    agent.run("Find a time")
    assert "no availability has been verified" in agent.run("What about Mei?")
    agent.reset()
    agent.run("hello")
    assert [m["role"] for m in model.calls[-1]] == ["system", "user"]


def test_history_is_bounded_and_isolated():
    agent = SchedulingAgent(FakeModel([final("done")], loop_last=True), Store.load())
    for i in range(12):
        agent.run(str(i))
    assert len(agent.turns) == 10
    assert SchedulingAgent(FakeModel([]), Store.load()).turns == []


def test_prompt_uses_dynamic_settings(monkeypatch):
    monkeypatch.setattr(slots, "SLOT_MINUTES", 10)
    prompt = build_system_prompt(Store.load().people, "2026-11-02")
    assert "10-minute" in prompt and "Priya Raman" in prompt
    assert "09:00" in prompt and "17:00" in prompt


@pytest.mark.parametrize("user_request,attendees", [
    ("Find an hour for Priya and Sam on Tuesday afternoon", ["priya"]),
    ("Find an hour with Priyaa and Samm on Tuesday", ["priya"]),
    ("Could Priya meet Sam on Tuesday?", ["priya"]),
    ("Find an hour with Priya on Tuesday", ["priya", "sam"]),
    ("Find an hour with Priya and Ghost on Tuesday", ["priya"]),
])
def test_model_cannot_drop_or_add_requested_attendees(user_request, attendees):
    model = FakeModel([schedule(attendees=attendees), final("done")])
    answer = SchedulingAgent(model, Store.load()).run(user_request)
    assert answer.startswith("Unable to complete the request:")
    assert "Availability for" not in answer
    assert len(model.calls) == (0 if "Ghost" in user_request else 1)


def test_time_only_follow_up_cannot_drop_previous_attendee():
    model = FakeModel([schedule(), final("done"), schedule(attendees=["priya"]), final("done")])
    agent = SchedulingAgent(model, Store.load())
    agent.run("Find an hour with Priya and Sam on Tuesday")
    assert "do not match" in agent.run("What about after 16:00?")


def test_explicit_new_group_replaces_old_group():
    model = FakeModel([schedule(), final("done"), schedule(attendees=["mei"]), final("done")])
    agent = SchedulingAgent(model, Store.load())
    agent.run("Find an hour with Priya and Sam on Tuesday")
    assert "Mei Tanaka" in agent.run("What about Mei?")
    agent.reset()
    assert agent.attendees == []


@pytest.mark.parametrize("response", [
    final("Ghost is not in the directory."),
    tool_call("get_busy_times", person="sam", date="2026-11-03"),
    schedule(attendees=["sam"]),
    tool_call("list_people"),
])
@pytest.mark.parametrize("user_request", [
    "Find 30 minutes with Sam and Ghost on Tuesday",
    "Find 30 minutes with Sam on Tuesday and with Ghost",
    "Find 30 minutes with Sam and with Ghost on Tuesday",
])
def test_unknown_person_reported_before_any_model_action(response, user_request):
    model = FakeModel([response, final("done")])
    answer = SchedulingAgent(model, Store.load()).run(user_request)
    assert "Employee not found in the directory: Ghost" in answer
    assert "Availability for" not in answer
    assert model.calls == []


def test_unknown_follow_up_is_reported_without_reusing_previous_result():
    model = FakeModel([schedule(), final("done")])
    agent = SchedulingAgent(model, Store.load())
    agent.run("Find an hour with Priya and Sam on Tuesday")
    answer = agent.run("What about Ghost?")
    assert "Employee not found in the directory: Ghost" in answer
    assert len(model.calls) == 2
    assert agent.attendees == ["priya", "sam"]


@pytest.mark.parametrize("raw,key", [
    ('{"tool":"missing","tool":"list_people","args":{}}', "tool"),
    ('{"final":"first","final":"done"}', "final"),
    ('{"tool":"list_people","args":{"extra":1},"args":{}}', "args"),
    ('{"tool":"find_free_slots","args":{"attendees":["sam"],"date":"2026-11-03",'
     '"duration_minutes":60,"duration_minutes":15}}', "duration_minutes"),
    ('{"tool":"list_people","args":{"nested":{"value":1,"value":2}}}', "value"),
    (r'{"tool":"list_people","args":{"x":1,"\u0078":2}}', "x"),
    ('{"tool":"list_people","args":{"nested":[{"value":1,"value":1}]}}', "value"),
])
def test_duplicate_json_keys_rejected_before_tool_execution(monkeypatch, raw, key):
    def unexpected_tool(*args, **kwargs):
        pytest.fail("Duplicate keys must be rejected before executing a tool")

    monkeypatch.setattr("scheduler.agent.TOOLS", {
        "list_people": unexpected_tool, "find_free_slots": unexpected_tool,
    })
    answer = SchedulingAgent(FakeModel([raw]), Store.load()).run("Find a time")
    assert answer == f"Unable to complete the request: Duplicate JSON key: {key}."


def test_duplicate_keys_after_lookup_do_not_publish_stale_availability():
    model = FakeModel([schedule(), '{"final":"done","final":"other"}'])
    answer = SchedulingAgent(model, Store.load()).run("Find an hour with Priya and Sam")
    assert "Duplicate JSON key: final" in answer
    assert "Availability for" not in answer
