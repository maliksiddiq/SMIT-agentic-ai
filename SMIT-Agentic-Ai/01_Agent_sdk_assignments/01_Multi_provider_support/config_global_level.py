import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_default_openai_client, set_tracing_disabled

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# Ek hi jagah set karo — poore app me ye client default ban jayega
set_default_openai_client(client)
set_tracing_disabled(True)

model = OpenAIChatCompletionsModel(model=os.getenv("GEMINI_MODEL"), openai_client=client)
agent = Agent(name="Assistant", instructions="Be concise.", model=model)

result = Runner.run_sync(agent, "What is 2+2?")
print(result.final_output)