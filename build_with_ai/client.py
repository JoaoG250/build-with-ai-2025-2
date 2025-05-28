import asyncio
import logging
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
        self._connected = False

    async def connect_to_server(self, server_module_name: str):
        """Conecta-se a um servidor MCP

        Este método inicializa uma conexão com um servidor MCP especificado pelo nome do módulo,
        utilizando parâmetros de servidor padrão. Ele cria uma sessão cliente, inicializa a sessão
        e exibe as ferramentas disponíveis fornecidas pelo servidor após a conexão ser estabelecida.

        Args:
            server_module_name: Nome do módulo Python para o servidor
        """

        if self._connected:
            logging.warning("Já conectado a um servidor MCP.")
            return

        logging.info(f"Conectando ao servidor MCP: {server_module_name}...")
        server_params = StdioServerParameters(
            command="uv", args=["run", "python", "-m", server_module_name], env=None
        )

        self.stdio, self.write = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()
        self._connected = True

        response = await self.session.list_tools()
        logging.info(
            "\nConectado ao servidor com as seguintes ferramentas:",
            [tool.name for tool in response.tools],
        )

    async def __get_tools_list(self) -> types.ToolListUnion:
        """
        Obtém a lista de ferramentas disponíveis no servidor MCP

        Retorna uma lista de objetos `Tool` que contêm declarações de função
        com nome, descrição e parâmetros.

        Returns:
            List[types.Tool]: Lista de ferramentas disponíveis no servidor MCP.
        Raises:
            ValueError: Se não houver sessão ativa com o servidor MCP.
        """

        if not self._connected or not self.session:
            raise ValueError("Erro, não conectado a um servidor MCP.")

        tools_list = await self.session.list_tools()
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters=types.Schema(**tool.inputSchema),
                    )
                ]
            )
            for tool in tools_list.tools
        ]

    def __get_gemini_reponse(
        self, contents: list[types.Content], tools: types.ToolListUnion
    ) -> types.GenerateContentResponse:
        """
        Obtém a resposta do Gemini

        Este método envia o histórico da conversa e as ferramentas disponíveis
        para o modelo Gemini e retorna a resposta gerada.

        Args:
            contents (list[types.Content]): Histórico da conversa a ser enviado ao modelo.
            tools (types.ToolListUnion): Lista de ferramentas disponíveis para o modelo.
        Returns:
            types.GenerateContentResponse: Resposta gerada pelo modelo Gemini.
        """

        return self.gemini_client.models.generate_content(
            model="gemini-2.5-pro-preview-05-06",
            contents=contents,
            config=types.GenerateContentConfig(tools=tools),
        )

    async def process_query(self, query: str) -> str:
        """
        Processa a consulta do usuário e retorna a resposta do Gemini

        Este método envia a consulta do usuário para o modelo Gemini, processa a resposta
        e executa chamadas de função se necessário. Ele mantém o histórico da conversa
        e retorna o texto final gerado pelo modelo.

        Args:
            query (str): A consulta do usuário a ser processada.
        Returns:
            str: O texto final gerado pelo modelo Gemini após processar a consulta.
        """

        if not self._connected or not self.session:
            return "Erro, não conectado a um servidor MCP."

        final_text: list[str] = []
        conversation_history: list[types.Content] = []

        # Adiciona a consulta do usuário ao histórico da conversa
        conversation_history.append(
            types.Content(role="user", parts=[types.Part(text=query)])
        )

        # Obtém a lista de ferramentas disponíveis no servidor MCP
        tools_definition = await self.__get_tools_list()

        # Obtém a resposta do Gemini com o histórico da conversa e as ferramentas
        gemini_response = self.__get_gemini_reponse(
            contents=conversation_history,
            tools=tools_definition,
        )

        # Adiciona a resposta do Gemini ao histórico da conversa
        if gemini_response.candidates and gemini_response.candidates[0].content:
            conversation_history.append(gemini_response.candidates[0].content)

        # Checa se há chamadas de função na resposta do Gemini
        function_call: types.FunctionCall | None = None
        if gemini_response.function_calls and len(gemini_response.function_calls) > 0:
            function_call = gemini_response.function_calls[0]

        # Se houver uma chamada de função, chama a ferramenta correspondente
        if function_call and function_call.name:
            function_call_result = await self.session.call_tool(
                name=function_call.name, arguments=function_call.args
            )
            logging.debug(
                f"[Chamando ferramenta {function_call.name} com os argumentos {function_call.args}]"
            )

            # Adiciona a chamada de função ao histórico da conversa
            conversation_history.append(
                types.Content(
                    role="model", parts=[types.Part(function_call=function_call)]
                )
            )

            for content in function_call_result.content:
                if isinstance(content, MCPTypes.TextContent):
                    # Adiciona o resultado da função ao histórico da conversa
                    conversation_history.append(
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_function_response(
                                    name=function_call.name,
                                    response={"result": content.text},
                                )
                            ],
                        )
                    )

            # Obtém a resposta do Gemini novamente com o histórico atualizado
            second_gemini_response = self.__get_gemini_reponse(
                contents=conversation_history,
                tools=tools_definition,
            )

            if (
                second_gemini_response.candidates
                and second_gemini_response.candidates[0].content
            ):
                # Adiciona a nova resposta do Gemini ao histórico da conversa
                conversation_history.append(
                    second_gemini_response.candidates[0].content
                )
                if second_gemini_response.text:
                    # Adiciona o texto da resposta do Gemini ao resultado final
                    final_text.append(second_gemini_response.text)

        # Se não houver chamada de função, apenas adiciona o texto da resposta do Gemini
        elif gemini_response.text:
            final_text.append(gemini_response.text)

        return "\n".join(final_text)

    async def chat_loop(self):
        """
        Inicia o loop de chat com o usuário

        Este método permite que o usuário interaja com o cliente MCP, enviando prompts
        e recebendo respostas do modelo Gemini. O loop continua até que o usuário digite
        'quit' para sair. Ele também lida com erros durante o processamento das consultas.
        """

        print("\nCliente MCP iniciado.")
        print("Digite seu prompt ou 'quit' para sair.\n")

        while True:
            try:
                query = input("\nPrompt: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                logging.error(f"\nErro: {str(e)}")

    async def cleanup(self):
        """Limpa recursos e fecha a sessão do cliente MCP"""
        if self._connected:
            logging.info("Fechando a sessão do cliente MCP...")
            try:
                await self.exit_stack.aclose()
                logging.info("Sessão do cliente MCP fechada com sucesso.")
            except Exception as e:
                logging.error(f"Erro ao fechar a sessão do cliente MCP: {str(e)}")
            finally:
                self._connected = False
                self.session = None
                self.exit_stack = AsyncExitStack()


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
