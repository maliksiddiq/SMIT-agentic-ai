import asyncio
import json
import os
from dataclasses import dataclass, field, asdict

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    function_tool,
    RunContextWrapper,
    ModelSettings,
    trace,
    set_tracing_export_api_key,
    handoff,
)

# Main Content: This is a study buddy application that uses OpenAI's API to quiz students on various topics. It includes features for tracking student performance, providing remedial tutoring, and managing session flow.

GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

load_dotenv()

client = AsyncOpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url=GEMINI_BASE_URL,
    max_retries=0,
)
model = OpenAIChatCompletionsModel(model=GEMINI_MODEL, openai_client=client)

# --- Milestone 7: tracing on (no set_tracing_disabled) ---
api_key = os.environ.get("OPENAI_API_KEY")
if api_key:
    set_tracing_export_api_key(api_key)
else:
    print("[tracing] OPENAI_API_KEY not set -> traces recorded locally; set it to export to platform.openai.com/traces")

MAX_TURNS = 6  # a normal cycle needs ~3 LLM calls (ask, grade, record); 6 gives headroom

with open("topics.json", "r", encoding="utf-8") as f:
    TOPICS = json.load(f)


@dataclass
class StudentProfile:
    name: str
    level: str  # "beginner" or "intermediate"
    weak_topics: list[str] = field(default_factory=list)
    answered: dict[str, dict[str, int]] = field(default_factory=dict)  # topic_id -> {"correct": n, "total": n}


PROFILE_PATH = "student_profile.json"


def load_profile() -> StudentProfile:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return StudentProfile(name=d["name"], level=d["level"],
                              weak_topics=d.get("weak_topics", []), answered=d.get("answered", {}))
    return StudentProfile(name="Student", level="beginner", weak_topics=[], answered={})


def save_profile(p: StudentProfile) -> None:
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(p), f, indent=2)


def notes_for(topic_id: str) -> str:
    topic = next((t for t in TOPICS if t["id"] == topic_id), None)
    if topic is None:
        return f"No topic found with id '{topic_id}'."
    facts = "\n".join(f"- {fact}" for fact in topic["key_facts"])
    return f"Title: {topic['title']}\nSummary: {topic['summary']}\nKey facts:\n{facts}"


@function_tool
def list_topics() -> str:
    """Return the list of available study topics with their ids and titles."""
    return "\n".join(f"{t['id']}: {t['title']}" for t in TOPICS)


@function_tool
def get_notes(topic_id: str) -> str:
    """Return the summary and key facts for a given topic id."""
    return notes_for(topic_id)


@function_tool
def record_answer(ctx: RunContextWrapper[StudentProfile], topic_id: str, was_correct: bool) -> str:
    """Record a student's quiz answer for a topic. Updates the profile's answered tally."""
    stats = ctx.context.answered.setdefault(topic_id, {"correct": 0, "total": 0})
    stats["total"] += 1
    if was_correct:
        stats["correct"] += 1
    return f"Recorded {topic_id} for {ctx.context.name}: {stats['correct']}/{stats['total']} correct."


# --- Milestone 9: Remedial Tutor + handoff ---
remedial = Agent(
    name="Remedial Tutor",
    instructions=(
        "You teach, you do not quiz. Explain the topic from first principles and walk through ONE "
        "worked example. Do not ask the student any questions; just teach."
    ),
    model=model,
)
remedial_handoff = handoff(remedial)  # tool name follows the agent name


@function_tool
def start_exam_mode(ctx: RunContextWrapper[StudentProfile]) -> str:
    """Start an exam-style session (only offered to intermediate students)."""
    return f"Exam mode started for {ctx.context.name}."


@function_tool
def finish_session(ctx: RunContextWrapper[StudentProfile]) -> str:
    """End the session and return a final summary. This is the last thing the tutor says."""
    lines = [f"Session summary for {ctx.context.name} ({ctx.context.level}):"]
    for tid, s in ctx.context.answered.items():
        acc = (s["correct"] / s["total"]) if s["total"] else 0
        lines.append(f"  {tid}: {s['correct']}/{s['total']} ({acc:.0%})")
    return "\n".join(lines)


def build_instructions(ctx: RunContextWrapper[StudentProfile], agent: Agent[StudentProfile]) -> str:
    p = ctx.context
    out = [f"You are {agent.name}, tutoring {p.name}, a {p.level} student."]
    if p.weak_topics:
        out.append(f"Prioritize these weak topics: {', '.join(p.weak_topics)}.")
    for tid, s in p.answered.items():
        if s["total"]:
            acc = s["correct"] / s["total"]  # difficulty decided in PYTHON, not by the model
            if acc > 0.70:
                out.append(f"{tid}: accuracy {acc:.0%} - ask HARDER questions.")
            else:
                out.append(f"{tid}: accuracy {acc:.0%} - keep drilling the basics.")
    # M9 routing rule, on its own line, numeric threshold
    out.append("If the student has 2 or more wrong answers on the current topic, hand off to the Remedial Tutor immediately.")
    out.append("Ask one question at a time; wait for the answer, then grade it.")
    out.append("You NEVER write or answer the quiz question yourself - always call question_writer, then grader, then record_answer.")
    out.append("When you call question_writer, include the topic id AND the key facts from get_notes so the question is about the OpenAI Agents SDK.")
    out.append("If the student wants to end the session, call finish_session.")
    return "\n".join(out)


question_writer = Agent(
    name="Question Writer",
    instructions="Write EXACTLY ONE quiz question about the OpenAI Agents SDK concept described in your input (which includes a topic id and its key facts). No preamble, no answer.",
    model=model,
    model_settings=ModelSettings(temperature=0.9),
)

grader = Agent(
    name="Grader",
    instructions=(
        "The single input has three sections: QUESTION, ANSWER, KEY FACTS. "
        "Return a verdict (CORRECT / PARTIAL / INCORRECT) followed by exactly ONE sentence of feedback. "
        "Be brief. You never see the student's name or profile; use only the provided text."
    ),
    model=model,
    model_settings=ModelSettings(temperature=0.1, max_tokens=120),
)

qw_tool = question_writer.as_tool(tool_name="question_writer",
    tool_description="Generate exactly one quiz question for a topic. Input is one string with the topic id and its key facts.")
gr_tool = grader.as_tool(tool_name="grader",
    tool_description="Grade a student answer. Input is one string with sections QUESTION:, ANSWER:, KEY FACTS:.")

# M11: exam mode only for intermediate students
start_exam_mode.is_enabled = lambda ctx, agent: ctx.context.level == "intermediate"

tutor = Agent(
    name="Study Buddy",
    instructions=build_instructions,
    model=model,
    tools=[list_topics, get_notes, record_answer, qw_tool, gr_tool, start_exam_mode, finish_session],
    handoffs=[remedial_handoff],
    tool_use_behavior="stop_on_first_tool",  # M11: a tool call ends the turn; finish_session ends the run
)


# --- quiz steps (one tool call per Runner.run, because tool_use_behavior=StopAtTools) ---
async def ask_question(topic_id: str, profile: StudentProfile):
    # returns the RunResult so the caller can inspect result.last_agent (handoff detection)
    return await Runner.run(tutor, f"Quiz me on {topic_id}.", context=profile, max_turns=MAX_TURNS)


async def grade_only(topic_id: str, question: str, answer: str, profile: StudentProfile) -> str:
    facts = notes_for(topic_id)
    prompt = f"Grade this.\nQUESTION: {question}\nANSWER: {answer}\nKEY FACTS: {facts}"
    saved = tutor.model_settings
    tutor.model_settings = ModelSettings(tool_choice="required")  # M5: force the grader call
    try:
        r = await Runner.run(tutor, prompt, context=profile, max_turns=MAX_TURNS)
    finally:
        tutor.model_settings = saved
    return r.final_output


async def record_only(topic_id: str, was_correct: bool, profile: StudentProfile) -> str:
    r = await Runner.run(tutor, f"Record the answer for topic {topic_id}, was_correct={was_correct}.",
                         context=profile, max_turns=MAX_TURNS)
    return r.final_output


async def run_cycle(topic_id: str, answer: str, profile: StudentProfile) -> None:
    with trace("Study session"):  # M7: one cycle = one trace
        r = await ask_question(topic_id, profile)
        if r.last_agent.name == "Remedial Tutor":  # M9: tutor handed off
            print("\n[remediation] Tutor handed off -> Remedial Tutor explains from first principles.")
            # M10: continue with the specialist for two more turns via to_input_list (no restart)
            r = await Runner.run(r.last_agent, r.to_input_list(), context=profile, max_turns=MAX_TURNS)
            print("Remedial Tutor:", r.final_output)
            r = await Runner.run(remedial, r.to_input_list(), context=profile, max_turns=MAX_TURNS)
            print("Remedial Tutor:", r.final_output)
            # deliberate route back to the main tutor with a fresh quiz on the same topic
            r = await ask_question(topic_id, profile)
            print("\n(Back to tutor) QUESTION:", r.final_output)
            question = r.final_output
        else:
            question = r.final_output
        print("\nQUESTION:", question)
        verdict = await grade_only(topic_id, question, answer, profile)
        print("VERDICT:", verdict)
        was_correct = "INCORRECT" not in verdict.upper()
        rec = await record_only(topic_id, was_correct, profile)
        print("RECORD:", rec)
    print("running tally:", profile.answered)


def print_summary(profile: StudentProfile) -> None:
    print("\n=== Session summary ===")
    if not profile.answered:
        print("No questions answered yet.")
    else:
        for tid, s in profile.answered.items():
            acc = (s["correct"] / s["total"]) if s["total"] else 0
            print(f"  {tid}: {s['correct']}/{s['total']} correct ({acc:.0%})")
    save_profile(profile)
    print(f"[profile saved to {PROFILE_PATH}]")


async def cli() -> None:
    profile = load_profile()
    print(f"Welcome back, {profile.name} ({profile.level}). Weak topics: {profile.weak_topics or 'none'}")
    while True:
        print("\n1) Pick a topic   2) Let tutor pick a weak topic   f) Finish   q) Quit")
        choice = input("> ").strip()
        if choice.lower() == "q":
            print_summary(profile)
            return
        if choice.lower() == "f":
            r = await Runner.run(tutor, "Finish the session.", context=profile, max_turns=MAX_TURNS)
            print("\n" + r.final_output)
            return
        if choice == "1":
            for t in TOPICS:
                print(f"  {t['id']}: {t['title']}")
            topic_id = input("Topic id: ").strip()
        elif choice == "2":
            topic_id = profile.weak_topics[0] if profile.weak_topics else TOPICS[0]["id"]
            print(f"Tutor picks: {topic_id}")
        else:
            continue
        await run_cycle(topic_id, input("Your answer: "), profile)


if __name__ == "__main__":
    asyncio.run(cli())
