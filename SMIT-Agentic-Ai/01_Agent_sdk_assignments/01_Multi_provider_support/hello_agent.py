import os
import warnings
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
)



load_dotenv()



gemini_client = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

model = OpenAIChatCompletionsModel(
    model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
    openai_client=gemini_client,
)

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant. Reply in one short sentence.",
    model=model,
)

result = Runner.run_sync(agent, "Say hello and tell me about agentic ai.")
print(result.final_output)
