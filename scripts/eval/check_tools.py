import asyncio
import httpx

async def check():
    async with httpx.AsyncClient() as client:
        # Create session
        res = await client.post("http://localhost:8000/sessions", json={"id": "test_tools", "title": "test"})
        
        # Chat
        res = await client.post("http://localhost:8000/chat/completions", json={
            "messages": [{"role": "user", "content": "Please list out the names of the tools you have access to right now."}],
            "conversationId": "test_tools",
            "stream": False
        }, timeout=30.0)
        
        print(res.json().get("choices", [{}])[0].get("message", {}).get("content"))

if __name__ == "__main__":
    asyncio.run(check())
