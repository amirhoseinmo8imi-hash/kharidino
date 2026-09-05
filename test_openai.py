import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY در فایل .env پیدا نشد."
    )

client = OpenAI(api_key=api_key)

response = client.responses.create(
    model=model,
    input="Say exactly: KHARIDINO AI OK"
)

print(response.output_text)