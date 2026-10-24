import main
from scheduler.model import FakeModel, final, tool_call


def test_interactive_follow_ups_and_new_session(monkeypatch, capsys):
    monkeypatch.setenv("LLM_BASE_URL", "http://unused")
    monkeypatch.setenv("LLM_MODEL", "unused")
    model = FakeModel([
        tool_call("find_free_slots", attendees=["sam"], date="2026-11-03", duration_minutes=45),
        final("done"), final("done"), final("done"),
    ])
    monkeypatch.setattr("scheduler.real_model.OpenAICompatibleModel", lambda: model)
    monkeypatch.setattr("sys.argv", ["main.py", "--interactive", "--real-model"])
    inputs = iter(["Find 45 minutes for Sam", "What about Mei?", "/new", "hello", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    main.main()
    output = capsys.readouterr().out
    assert "45 minutes" in output and "Started a new conversation" in output
    assert len([m for m in model.calls[2] if m["role"] == "user"]) == 2
    assert len(model.calls[3]) == 2


def test_scripted_demo_clearly_identified(monkeypatch, capsys):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["main.py", "anything"])
    main.main()
    assert "Scripted demo:" in capsys.readouterr().out


def test_interactive_works_offline_with_follow_ups(monkeypatch, capsys):
    # Even configured endpoints must not replace the offline default.
    monkeypatch.setenv("LLM_BASE_URL", "http://must-not-be-called")
    monkeypatch.setenv("LLM_MODEL", "unused")
    monkeypatch.setattr("sys.argv", ["main.py", "-i"])
    inputs = iter(["Find 45 minutes with Priyaa and Samm on Tuesday afternoon",
                   "What about after 16:00?", "Now check Mei and Luis before noon",
                   "/new", "What about after 16:00?", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    main.main()
    output = capsys.readouterr().out
    assert "Offline FakeModel" in output
    assert "Priya Raman, Sam Okafor" in output
    assert "16:15–17:00" in output
    assert "Mei Tanaka, Luis Moreno" in output
    assert "no availability has been verified" in output
