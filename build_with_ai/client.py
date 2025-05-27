import asyncio
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp import types as MCPTypes


class MCPClient:
    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    async def connect_to_server(self, server_module_name: str):
        """Connect to an MCP server

        Args:
            server_module_name: Python module name for the server
        """

        server_params = StdioServerParameters(
            command="uv", args=["run", "python", "-m", server_module_name], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])
        for tool in tools:
            print(tool.description)
            print(tool.inputSchema)

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""

        if not self.session:
            return "Error, no client session available"

        response = await self.session.list_tools()
        tools_definition: types.ToolListUnion = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters=types.Schema(**tool.inputSchema),
                    )
                ]
            )
            for tool in response.tools
        ]

        gemini_response = self.gemini_client.models.generate_content(
            model="gemini-2.5-pro-preview-05-06",
            contents=query,
            config=types.GenerateContentConfig(
                temperature=0,
                tools=tools_definition,
            ),
        )
        print("Response from gemini: " + str(gemini_response.to_json_dict()))

        # Process response and handle tool calls
        final_text: list[str] = []

        def get_function_call(
            response: types.GenerateContentResponse,
        ) -> types.FunctionCall | None:
            if (
                response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
            ):
                return response.candidates[0].content.parts[0].function_call
            return None

        if gemini_response.text:
            final_text.append(gemini_response.text)

        function_call = get_function_call(gemini_response)
        if function_call and function_call.name:
            function_call_result = await self.session.call_tool(
                name=function_call.name, arguments=function_call.args
            )
            final_text.append(
                f"[Calling tool {function_call.name} with args {function_call.args}]"
            )
            for content in function_call_result.content:
                if isinstance(content, MCPTypes.TextContent):
                    final_text.append(content.text)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server("build_with_ai.server")
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
