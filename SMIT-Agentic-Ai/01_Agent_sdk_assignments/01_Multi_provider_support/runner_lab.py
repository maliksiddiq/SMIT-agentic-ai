import asyncio
from dotenv import load_dotenv
import os
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("GEMINI_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
model = OpenAIChatCompletionsModel(model=os.getenv("GEMINI_MODEL"), openai_client=client)
agent = Agent(name="Assistant", instructions="Be concise.", model=model)

def demo_sync():
    result = Runner.run_sync(agent, "Tell me a fact about Mars.")
    print("[sync]", result.final_output, "| agent:", result.last_agent.name, "| items:", len(result.new_items))

async def demo_async():
    result = await Runner.run(agent, "Tell me a fact about the Moon.")
    print("[async]", result.final_output, "| agent:", result.last_agent.name, "| items:", len(result.new_items))

async def demo_streamed():
    result = Runner.run_streamed(agent, "Tell me a fact about Jupiter.")
    print("[streamed] ", end="", flush=True)
    async for event in result.stream_events():
        if event.type == "raw_response_event" and hasattr(event.data, "delta"):
            print(event.data.delta, end="", flush=True)
    print()
    print("agent:", result.last_agent.name, "| items:", len(result.new_items))

if __name__ == "__main__":
    asyncio.run(demo_async())
    asyncio.run(demo_streamed())
    demo_sync()
