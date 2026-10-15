"""Send one message to Groq and print the reply. Proves the API works."""
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "user", "content": "Reply with exactly: hello from Groq"}
    ],
)

print(response.choices[0].message.content)