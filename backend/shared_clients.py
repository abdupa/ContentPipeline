import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the OpenAI client in this central location
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
