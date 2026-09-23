import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel

load_dotenv()

provider = os.getenv("MODEL_PROVIDER", "gemini")

if provider == "gemini":
    client = AsyncOpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
else:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model_name = "gpt-4o-mini"

model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)

# Ye Agent dono providers ke liye BYTE-FOR-BYTE same hai
agent = Agent(
    name="Assistant",
    instructions="You are a helpful, concise assistant.",
    model=model,
)

if __name__ == "__main__":
    result = Runner.run_sync(agent, "What is the capital of France?")
    print(result.final_output)