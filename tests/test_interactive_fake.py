from scheduler.agent import SchedulingAgent
from scheduler.model import InteractiveFakeModel, FakeModel
from scheduler.store import Store


def test_offline_fake_reuses_and_replaces_constraints():
    model = InteractiveFakeModel()
    assert isinstance(model, FakeModel)
    agent = SchedulingAgent(model, Store.load())
    assert "45 minutes" in agent.run("Find 45 minutes with Priyaa and Samm on Tuesday afternoon")
    answer = agent.run("What about after 16:00?")
    assert "16:00–16:45" in answer and "13:00" not in answer
    answer = agent.run("Now check Mei and Luis before noon")
    assert "Mei Tanaka, Luis Moreno" in answer and "09:00–09:45" in answer
    assert "Priya" not in answer
    assert "2026-11-04" in agent.run("What about Wednesday?")
    assert "15 minutes" in agent.run("Try 15 minutes instead")


def test_offline_fake_unknown_people_and_reset():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    assert "ghost" in agent.run("Find 30 minutes with Sam and ghost on Tuesday")
    agent.reset()
    assert "no availability has been verified" in agent.run("After 16:00")


def test_offline_fake_directory_and_unrelated_questions():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    assert "Employees:" in agent.run("list people")
    agent.run("Find an hour for Sam tomorrow morning")
    assert "no availability has been verified" in agent.run("hello")


def test_offline_fake_rejects_unsupported_time_bounds():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    agent.run("Find 45 minutes with Sam on Tuesday")
    assert "Times must use HH:MM" in agent.run("Check Mei before 5pm")
    assert "Times must use HH:MM" in agent.run("Check Mei between nine and noon")


def test_afternoon_does_not_override_explicit_lower_bound():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    answer = agent.run("Find 45 minutes with Priya and Sam on Tuesday afternoon after 16:00")
    assert answer.endswith("16:00–16:45, 16:15–17:00.")
    assert "13:00" not in answer


def test_morning_does_not_override_explicit_upper_bound():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    answer = agent.run("Find 45 minutes with Mei on Tuesday morning before 10:00")
    assert answer.endswith("09:00–09:45, 09:15–10:00.")
    assert "10:00–" not in answer


def test_conflicting_period_and_explicit_bound_is_rejected():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    answer = agent.run("Find 45 minutes with Mei on Tuesday afternoon before 10:00")
    assert "Bounds must be ordered" in answer


def test_offline_unknown_second_clause_is_not_silently_dropped():
    model = InteractiveFakeModel()
    agent = SchedulingAgent(model, Store.load())
    answer = agent.run("Find 30 minutes with Sam on Tuesday and with Ghost")
    assert "Employee not found in the directory: Ghost" in answer
    assert model.calls == []


def test_decimal_hours_are_converted_without_losing_the_fraction():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    answer = agent.run("Find 1.5 hours with Sam on Tuesday before noon")
    assert "90 minutes" in answer and "09:30–11:00" in answer


def test_repeated_bounds_do_not_offer_earlier_times():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    answer = agent.run("Find 45 minutes with Priya and Sam on Tuesday after 12:00 and after 16:00")
    assert answer.endswith("16:00–16:45, 16:15–17:00.")


def test_subject_first_request_works_offline():
    agent = SchedulingAgent(InteractiveFakeModel(), Store.load())
    answer = agent.run("Priya and Sam need 45 minutes on Tuesday afternoon")
    assert "Priya Raman, Sam Okafor" in answer and "45 minutes" in answer
