import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

response = client.chat.completions.create(
    model="spark-x",
    messages=[{"role": "user", "content": "你好"}],
    max_tokens=100,
)
print("✅ 响应:", response.choices[0].message.content)