import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
model = OpenAIChatCompletionsModel(model=os.getenv("GEMINI_MODEL"), openai_client=client)

# Model seedha Agent ke andar diya gaya hai
agent = Agent(name="Assistant", instructions="Be concise.", model=model)

result = Runner.run_sync(agent, "What is 2+2?")
print(result.final_output)
