import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("GEMINI_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
model = OpenAIChatCompletionsModel(model=os.getenv("GEMINI_MODEL"), openai_client=client)
agent = Agent(name="Assistant", instructions="Be concise and friendly.", model=model)

history = []
print("Chat shuru — 'exit' likh ke band karo.")
while True:
    user_input = input("You: ")
    if user_input.strip().lower() == "exit":
        break
    result = Runner.run_sync(agent, history + [{"role": "user", "content": user_input}])
    print("Agent:", result.final_output)
    history = result.to_input_list()
