"""Single-request demo or interactive scheduling session."""

import argparse
import os

from scheduler.agent import SchedulingAgent
from scheduler.model import FakeModel, InteractiveFakeModel, final, tool_call
from scheduler.store import Store


def demo_model() -> FakeModel:
    return FakeModel([
        tool_call("find_free_slots", attendees=["priya", "sam"],
                  date="2026-11-03", duration_minutes=60, earliest="12:00"),
        final("done"),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="*")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Keep a conversation open for follow-up questions (offline fake by default).")
    parser.add_argument("--real-model", action="store_true",
                        help="Use the configured optional model in interactive mode.")
    args = parser.parse_args()
    real_model = bool(os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL"))
    if args.real_model and not real_model:
        parser.error("--real-model requires LLM_BASE_URL and LLM_MODEL.")
    if real_model and (not args.interactive or args.real_model):
        from scheduler.real_model import OpenAICompatibleModel
        model = OpenAICompatibleModel()
    elif args.interactive:
        print("Offline FakeModel: use names, dates/weekdays, minutes, and HH:MM bounds.")
        model = InteractiveFakeModel()
    else:
        print("Scripted demo: always checks Priya and Sam on Nov 3, regardless of input.")
        model = demo_model()
    agent = SchedulingAgent(model, Store.load())
    request = " ".join(args.request)
    if request or not args.interactive:
        print(agent.run(request or "Find an hour for Priya and Sam on Tuesday afternoon"))
    if args.interactive:
        print("Ask follow-ups; /new clears context; /quit exits.")
        while True:
            try:
                request = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if request == "/quit":
                break
            if request == "/new":
                agent.reset()
                print("Started a new conversation.")
            elif request:
                print(agent.run(request))


if __name__ == "__main__":
    main()
