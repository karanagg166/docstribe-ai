import os
from dotenv import load_dotenv
import cohere

def test_cohere_connection():
    load_dotenv()
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        print("Error: COHERE_API_KEY not found in environment.")
        return

    try:
        print("Initializing Cohere client...")
        co = cohere.ClientV2(api_key=api_key)
        print("Testing Cohere chat endpoint...")
        response = co.chat(
            model="command-r-plus-08-2024",
            messages=[{"role": "user", "content": "Hello, are you working?"}]
        )
        print("Cohere response received successfully!")
        print(f"Message: {response.message.content[0].text}")
        print("Success: Cohere API is working.")
    except Exception as e:
        print(f"Error testing Cohere: {e}")

if __name__ == "__main__":
    test_cohere_connection()
