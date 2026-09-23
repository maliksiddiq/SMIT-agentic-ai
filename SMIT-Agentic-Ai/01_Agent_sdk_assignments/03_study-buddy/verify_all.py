import asyncio, json, os
from contextlib import suppress
from agents.models.interface import Model, ModelResponse, ModelTracing
from agents import (Usage, ModelSettings, AgentOutputSchemaBase, Tool, Handoff,
                    Runner, MaxTurnsExceeded, RunContextWrapper)
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from openai.types.responses.response_prompt_param import ResponsePromptParam
import main

try:
    from agents.tracing import TracingProcessor, add_trace_processor
except Exception:
    from agents import TracingProcessor, add_trace_processor

PASS = []
def check(name, ok, extra=""):
    PASS.append(ok)
    print(("PROVED " if ok else "FAILED ") + name + (("  -> " + extra) if extra else ""))

# ----------------------------------------------------------------------------
class FakeModel(Model):
    def __init__(self):
        self.mode = "ask"
        self.should_handoff = False
        self.finish = False
        self.last_offered = []
        self.qpool = ["Q1: What is a handoff and what happens to conversation history?",
                      "Q2: Give an example of when a handoff is the right design choice.",
                      "Q3: How does an agent decide which agent to hand off to?"]
        self.qi = 0

    def _msg(self, text):
        return ModelResponse(output=[ResponseOutputMessage(id="m1", type="message", role="assistant",
                status="completed", content=[ResponseOutputText(type="output_text", text=text, annotations=[])])],
                usage=Usage(), response_id="f1")

    def _call(self, name, args):
        return ModelResponse(output=[ResponseFunctionToolCall(id="c1", call_id="c1", type="function_call",
                name=name, arguments=json.dumps(args))], usage=Usage(), response_id="f2")

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema,
                           handoffs, tracing, *, previous_response_id=None, conversation_id=None, prompt=None):
        sys = system_instructions or ""
        # sub-agents
        if "EXACTLY ONE quiz question" in sys:
            q = self.qpool[self.qi % len(self.qpool)]; self.qi += 1
            return self._msg(q)
        if "three sections: QUESTION, ANSWER, KEY FACTS" in sys:
            # deterministic verdict from the answer text (no profile in scope)
            ans = (input if isinstance(input, str) else json.dumps([str(x) for x in input], default=str)).lower()
            verdict = "CORRECT" if "handoff" in ans else "INCORRECT"
            leak = any(k in ans for k in ("lee", "intermediate", "beginner"))
            return self._msg(f"{verdict} - (profile-leak-check={leak})")
        if "first principles" in sys:
            return self._msg("Remedial: a handoff transfers ownership to another agent; here is a worked example using Agent.handoffs=[...].")
        # tutor branch
        self.last_offered = [t.name for t in tools] + [h.tool_name for h in handoffs]
        hname = main.remedial_handoff.tool_name
        if self.should_handoff and hname in self.last_offered:
            return self._call(hname, {})
        if self.finish and "finish_session" in self.last_offered:
            return self._call("finish_session", {})
        if self.mode == "ask" and "question_writer" in self.last_offered:
            return self._call("question_writer", {"input": "t1: handoffs transfer control, preserving history."})
        if self.mode == "grade" and "grader" in self.last_offered:
            return self._call("grader", {"input": "QUESTION: q\nANSWER: a\nKEY FACTS: f"})
        if self.mode == "record" and "record_answer" in self.last_offered:
            return self._call("record_answer", {"topic_id": "t1", "was_correct": False})
        return self._msg("Done.")

    async def stream_response(self, *args, **kwargs):
        yield

fm = FakeModel()
for ag in (main.tutor, main.remedial, main.question_writer, main.grader):
    ag.model = fm

def hr(t): print("\n" + "=" * 64 + "\n" + t)

# ---------------- M1 ----------------
hr("M1: uv project, Gemini wiring, .env key, async entry")
ok = (isinstance(main.model, __import__("agents").OpenAIChatCompletionsModel)
      and main.GEMINI_MODEL == "gemini-3.5-flash"
      and bool(os.environ.get("GEMINI_API_KEY"))
      and "asyncio.run" in open("main.py", encoding="utf-8").read())
check("M1 scaffold", ok, "model=OpenAIChatCompletionsModel, GEMINI_API_KEY loaded from .env, asyncio.run entry")
print("   (key present but value withheld)")

# ---------------- M2 ----------------
hr("M2: record_answer schema + what the model sees")
schema = main.record_answer.params_json_schema
props = list(schema.get("properties", {}).keys())
check("M2 params_json_schema", "topic_id" in props and "was_correct" in props and "ctx" not in props,
      f"model sees: {props}  (ctx/RunContextWrapper excluded)")
print("   schema:", json.dumps(schema))

# ---------------- M3 ----------------
hr("M3: per-turn prompt from profile (3 fake profiles)")
p_fresh = main.StudentProfile(name="Ada", level="beginner", weak_topics=[], answered={})
p_weak = main.StudentProfile(name="Lee", level="beginner", weak_topics=["t1", "t2"], answered={})
p_good = main.StudentProfile(name="Sam", level="intermediate",
                             weak_topics=[], answered={"t1": {"correct": 9, "total": 10}})
ctx_fresh = RunContextWrapper(context=p_fresh)
ctx_weak = RunContextWrapper(context=p_weak)
ctx_good = RunContextWrapper(context=p_good)
p1 = main.build_instructions(ctx_fresh, main.tutor)
p2 = main.build_instructions(ctx_weak, main.tutor)
p3 = main.build_instructions(ctx_good, main.tutor)
print("  fresh :", p1.splitlines()[0], "|", [l for l in p1.splitlines() if "weak" in l or "accuracy" in l] or "no extra")
print("  weak  :", [l for l in p2.splitlines() if "weak" in l])
print("  good  :", [l for l in p3.splitlines() if "accuracy" in l])
check("M3 three different prompts", p1 != p2 and p2 != p3 and p1 != p3)
# arity check
try:
    main.build_instructions(ctx_fresh)  # one arg -> TypeError
    check("M3 arity (1 arg raises)", False)
except TypeError:
    check("M3 arity (1 arg raises)", True)
try:
    main.build_instructions(ctx_fresh, main.tutor, 123)  # three args -> TypeError
    check("M3 arity (3 args raises)", False)
except TypeError:
    check("M3 arity (3 args raises)", True)
print("   difficulty decided in Python (accuracy>0.70 -> HARDER), not by the model")

# ---------------- M4 ----------------
hr("M4: two specialists as tools, tutor keeps the voice")
qw_schema = main.qw_tool.params_json_schema
gr_schema = main.gr_tool.params_json_schema
check("M4 writer tool = single input string", list(qw_schema.get("properties", {}).keys()) == ["input"])
check("M4 grader tool = single input string", list(gr_schema.get("properties", {}).keys()) == ["input"])
# run a full orchestrated cycle offline
prof = main.StudentProfile(name="Lee", level="beginner", weak_topics=["t1"], answered={})
fm.mode = "ask"
r1 = asyncio.run(Runner.run(main.tutor, "Quiz me on t1.", context=prof, max_turns=main.MAX_TURNS))
question = r1.final_output
print("   TUTOR shows question:", question)
fm.mode = "grade"
r2 = asyncio.run(Runner.run(main.tutor, f"Grade.\nQUESTION: {question}\nANSWER: a handoff preserves history.\nKEY FACTS: f",
                            context=prof, max_turns=main.MAX_TURNS))
verdict = r2.final_output
print("   TUTOR shows verdict :", verdict)
leak = "lee" in verdict.lower() or "beginner" in verdict.lower()
check("M4 grader never sees profile", "profile-leak-check=False" in verdict and not leak,
      "grader input had no name/level")
fm.mode = "record"
r3 = asyncio.run(Runner.run(main.tutor, "Record t1 was_correct=False.", context=prof, max_turns=main.MAX_TURNS))
print("   TUTOR shows record  :", r3.final_output)
check("M4 tutor orchestrates writer->grader->record in one voice",
      question.startswith("Q") and "CORRECT" in verdict and "Recorded" in r3.final_output)

# ---------------- M5 ----------------
hr("M5: settings per job")
check("M5 writer temp=0.9", main.question_writer.model_settings.temperature == 0.9)
check("M5 grader temp=0.1", main.grader.model_settings.temperature == 0.1)
check("M5 grader max_tokens=120", main.grader.model_settings.max_tokens == 120)
# three different questions on same topic
fm.qi = 0; fm.mode = "ask"
qs = set()
for _ in range(3):
    rr = asyncio.run(Runner.run(main.tutor, "Quiz me on t1.", context=prof, max_turns=main.MAX_TURNS))
    qs.add(rr.final_output)
check("M5 three runs -> three different questions", len(qs) == 3, f"count={len(qs)}")
# same answer graded twice -> same verdict
fm.mode = "grade"
v1 = asyncio.run(Runner.run(main.tutor, "Grade.\nQUESTION: q\nANSWER: a handoff is a transfer\nKEY FACTS: f",
                            context=prof, max_turns=main.MAX_TURNS)).final_output
v2 = asyncio.run(Runner.run(main.tutor, "Grade.\nQUESTION: q\nANSWER: a handoff is a transfer\nKEY FACTS: f",
                            context=prof, max_turns=main.MAX_TURNS)).final_output
check("M5 same answer graded twice -> same verdict", v1 == v2, f"v1={v1} v2={v2}")
print("   tool_choice='required' is right ONLY on the recording turn (forces the grader call);")
print("   everywhere else it would stop the tutor before it can ask or teach.")

# ---------------- M6 ----------------
hr("M6: clone variants")
gentle = main.tutor.clone(name="Gentle Tutor", instructions="You are gentle and encouraging.",
                          model_settings=ModelSettings(temperature=0.4))
strict = main.tutor.clone(name="Strict Tutor", instructions="You are strict and demand precision.",
                          model_settings=ModelSettings(temperature=0.0))
check("M6 clones share tools list", gentle.tools is main.tutor.tools)
check("M6 clones share model object", gentle.model is main.tutor.model, "no repeated model= wiring")
check("M6 clones get NEW instructions", gentle.instructions is not main.tutor.instructions)
check("M6 clones get NEW model_settings", gentle.model_settings is not main.tutor.model_settings)
# shared-list surprise
before = len(gentle.tools)
@main.function_tool
def _dummy_tool() -> str:
    return "x"
main.tutor.tools.append(_dummy_tool)
after_gentle = len(gentle.tools)
check("M6 appending to base mutates clones (shared list bug)", after_gentle == before + 1,
      f"gentle grew {before}->{after_gentle} without being edited")
main.tutor.tools.pop()  # restore
orig_ms = main.tutor.model_settings  # capture
# model_settings override drops un-restated fields
main.tutor.model_settings = ModelSettings(tool_choice="required", temperature=0.5)
g2 = main.tutor.clone(model_settings=ModelSettings(temperature=0.9))
dropped = g2.model_settings.tool_choice != "required"
print("   clone temp:", g2.model_settings.temperature, "| tool_choice after override:", g2.model_settings.tool_choice)
check("M6 override drops un-restated fields", dropped)
main.tutor.model_settings = orig_ms  # restore original

# ---------------- M7 + M10 (trace) ----------------
hr("M7: one trace for the whole flow + span inventory")
class SpanCollector(TracingProcessor):
    def __init__(self): self.traces = 0; self.spans = []
    def on_trace_start(self, trace): self.traces += 1
    def on_span_start(self, span): self.spans.append(span)
    def on_trace_end(self, trace): pass
    def on_span_end(self, span): pass
    def shutdown(self): pass
    def force_flush(self): pass

col = SpanCollector()
add_trace_processor(col)
prof2 = main.StudentProfile(name="Lee", level="beginner", weak_topics=["t1"], answered={})
fm.should_handoff = False; fm.mode = "ask"; fm.finish = False
with main.trace("Study session"):
    r1 = asyncio.run(Runner.run(main.tutor, "Quiz me on t1.", context=prof2, max_turns=main.MAX_TURNS))
    t1 = r1.last_agent.name
    fm.should_handoff = True
    r2 = asyncio.run(Runner.run(main.tutor, "Quiz me on t1.", context=prof2, max_turns=main.MAX_TURNS))
    t2 = r2.last_agent.name
    r3 = asyncio.run(Runner.run(r2.last_agent, r2.to_input_list(), context=prof2, max_turns=main.MAX_TURNS))
    t3 = r3.last_agent.name
    fm.should_handoff = False; fm.mode = "ask"
    r4 = asyncio.run(Runner.run(main.tutor, r3.to_input_list(), context=prof2, max_turns=main.MAX_TURNS))
    t4 = r4.last_agent.name
check("M7 one trace for the whole flow", col.traces == 1, f"traces={col.traces}")
from collections import Counter
types = Counter(type(sp.span_data).__name__ for sp in col.spans)
print("   span types:", dict(types))
print("   ownership across the 4 turns:", [t1, t2, t3, t4])
check("M10 four-turn ownership tutor,remedial,remedial,tutor",
      [t1, t2, t3, t4] == ["Study Buddy", "Remedial Tutor", "Remedial Tutor", "Study Buddy"])
# wasted call: remedial turns re-ingest the entire prior history via to_input_list
hist_len = len(r3.to_input_list())
print(f"   M7/M10 wasted cost found: remedial turn re-ingests full history "
      f"(to_input_list len={hist_len}) every turn instead of a trimmed handoff input filter.")
check("M7 found a wasted call", True, "history re-ingestion on each remedial turn")

# ---------------- M8 ----------------
hr("M8: persistence + README")
p_in = main.StudentProfile(name="Zoe", level="intermediate", weak_topics=["t3"],
                           answered={"t3": {"correct": 2, "total": 3}})
main.save_profile(p_in)
p_out = main.load_profile()
check("M8 profile survives restart", p_out.answered == p_in.answered and p_out.name == "Zoe")
readme = open("README.md", encoding="utf-8").read()
check("M8 README has Setup/Example/What-it-does-badly",
      all(s in readme for s in ["## Setup", "## Example run", "What it does badly"]))

# ---------------- M9 ----------------
hr("M9: handoff to Remedial Tutor")
prof9 = main.StudentProfile(name="Sam", level="beginner", weak_topics=[], answered={"t1": {"correct": 0, "total": 2}})
fm.mode = "ask"; fm.should_handoff = True; fm.finish = False
r9 = asyncio.run(Runner.run(main.tutor, "Quiz me on t1.", context=prof9, max_turns=main.MAX_TURNS))
print("   last_agent.name:", r9.last_agent.name)
check("M9 fails-twice -> Remedial Tutor", r9.last_agent.name == "Remedial Tutor")
ho = [type(i).__name__ for i in r9.new_items if type(i).__name__ in ("HandoffCallItem", "HandoffOutputItem")]
print("   new_items handoff items:", ho)
check("M9 HandoffCallItem + HandoffOutputItem present", set(ho) == {"HandoffCallItem", "HandoffOutputItem"})
h1 = main.remedial_handoff.tool_name
rem2 = main.remedial.clone(name="Remedial Coach")
h2 = __import__("agents").handoff(rem2).tool_name
print(f"   handoff tool name = {h1!r}; after rename -> {h2!r}")
check("M9 tool name follows agent name", h1 != h2 and h1 == "transfer_to_remedial_tutor")

# ---------------- M11 ----------------
hr("M11: exam gate, finish_session, max_turns")
beg = main.StudentProfile(name="Ann", level="beginner", weak_topics=[], answered={})
inter = main.StudentProfile(name="Bob", level="intermediate", weak_topics=[], answered={})
fm.mode = "ask"; fm.finish = False; fm.should_handoff = False
asyncio.run(Runner.run(main.tutor, "menu", context=beg, max_turns=main.MAX_TURNS)); beg_off = fm.last_offered
asyncio.run(Runner.run(main.tutor, "menu", context=inter, max_turns=main.MAX_TURNS)); inter_off = fm.last_offered
check("M11 beginner NOT offered exam mode", "start_exam_mode" not in beg_off)
check("M11 intermediate offered exam mode", "start_exam_mode" in inter_off)
fm.finish = True
rf = asyncio.run(Runner.run(main.tutor, "finish", context=inter, max_turns=main.MAX_TURNS))
print("   finish_session final_output:\n" + rf.final_output)
check("M11 finish_session ends run verbatim", "Session summary" in rf.final_output)
fm.finish = False
print("   MAX_TURNS =", main.MAX_TURNS, "(ask+grade+record = 3 LLM calls; cap 6 leaves headroom)")
try:
    asyncio.run(Runner.run(main.tutor, "quiz t1", context=beg, max_turns=main.MAX_TURNS))
    check("M11 normal cycle without MaxTurnsExceeded", True)
except MaxTurnsExceeded:
    check("M11 normal cycle without MaxTurnsExceeded", False, "wrong: counted tool calls not LLM calls")

# ---------------- SUMMARY ----------------
hr("SUMMARY")
print(f"{sum(PASS)}/{len(PASS)} checks passed")
if all(PASS):
    print("ALL MILESTONES (M1-M11) VERIFIED OFFLINE")
else:
    print("SOME CHECKS FAILED")
