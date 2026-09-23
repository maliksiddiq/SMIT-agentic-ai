import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, RunConfig

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
model = OpenAIChatCompletionsModel(model=os.getenv("GEMINI_MODEL"), openai_client=client)

# Is baar Agent me model nahi diya — RunConfig ke through diya jayega
agent = Agent(name="Assistant", instructions="Be concise.")
config = RunConfig(model=model)

result = Runner.run_sync(agent, "What is 2+2?", run_config=config)
print(result.final_output)
