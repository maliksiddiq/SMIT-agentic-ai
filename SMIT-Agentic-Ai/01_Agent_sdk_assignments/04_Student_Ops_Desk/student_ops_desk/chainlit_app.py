import chainlit as cl

from student_ops_desk.app import StudentOpsDesk, build_demo_profile, validate_startup
from student_ops_desk.models import Ticket


@cl.on_chat_start
async def start() -> None:
    validate_startup()
    profile = build_demo_profile()
    cl.user_session.set("profile", profile)
    cl.user_session.set("desk", StudentOpsDesk(profile))
    await cl.Message(
        content="# Saylani Student Ops Desk\nAsk about assignments, careers, schedules, or course policies.",
        author="Saylani Student Ops Desk",
    ).send()


@cl.on_message
async def handle_message(message: cl.Message) -> None:
    desk: StudentOpsDesk = cl.user_session.get("desk")
    result = await desk.answer(message.content)
    if isinstance(result, Ticket):
        content = (
            f"### Ticket\n"
            f"**Category:** {result.category}\n\n"
            f"**Summary:** {result.summary}\n\n"
            f"**Next step:** {result.next_step}\n\n"
            f"**Resolved:** {'Yes' if result.resolved else 'No'}\n\n"
            f"**Escalation required:** {'Yes' if result.escalate else 'No'}"
        )
        await cl.Message(content=content, author="Ticketing").send()
    else:
        await cl.Message(content=result, author="Saylani Student Ops Desk").send()
