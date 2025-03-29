import sys
import json
import asyncio
import logging
from dataclasses import dataclass
from contextlib import AsyncExitStack
from typing import Optional, List, Dict, Any, Tuple, AsyncGenerator
from tenacity import retry, stop_after_attempt, wait_exponential

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client

import groq
from dotenv import load_dotenv
import os

load_dotenv()  # load environment variables from .env

@dataclass
class GroqConfig:
    """Configuration for the GroqMCPClient."""
    api_key: str
    model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 1024
    temperature: float = 0.7
    max_retries: int = 3
    retry_wait_min: int = 1
    retry_wait_max: int = 10

class GroqMCPClient:
    """A client for interacting with MCP servers using Groq's LLM capabilities.
    
    This client manages communication with an MCP server and uses Groq's LLM to process
    queries and execute tools. It supports interactive chat and dynamic model switching.
    
    Attributes:
        session: The MCP client session for server communication
        exit_stack: Async context manager stack for resource cleanup
        groq_client: The Groq API client instance
        model: The current Groq model being used
        stdio: The standard I/O transport for server communication
        write: The write function for sending data to the server
    """
    
    def __init__(self, config: Optional[GroqConfig] = None):
        """Initialize the GroqMCPClient with required configurations.
        
        Args:
            config: Optional configuration object. If not provided, will load from environment.
            
        Raises:
            ValueError: If GROQ_API_KEY environment variable is not set
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.stdio: Optional[AsyncGenerator] = None
        self.write: Optional[callable] = None
        
        # Load configuration
        if config is None:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable is not set")
            config = GroqConfig(
                api_key=api_key,
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            )
        
        self.config = config
        self.groq_client = groq.Client(api_key=config.api_key)
        self.model = config.model
        
        self.logger.info(f"Initialized GroqMCPClient with model: {self.model}")

    async def connect_to_server(self, server_script_path: str) -> None:
        """Connect to an MCP server and initialize the session.
        
        Args:
            server_script_path: Path to the server script (.py or .js)
            
        Raises:
            ValueError: If server script is not a .py or .js file
        """
        self.logger.info(f"Connecting to server script: {server_script_path}")
        
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        try:
            # Set up communication with the server
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
            
            # Initialize the session
            await self.session.initialize()
            
            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            self.logger.info(f"Connected to server with tools: {[tool.name for tool in tools]}")
        except Exception as e:
            self.logger.error(f"Failed to connect to server: {str(e)}")
            raise

    def _convert_tool_schema(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert MCP tool schema to Groq format.
        
        Args:
            tools: List of MCP Tool objects
            
        Returns:
            List of dictionaries in Groq tool format
        """
        groq_tools = []
        for tool in tools:
            groq_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            groq_tools.append(groq_tool)
        return groq_tools

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _make_groq_api_call(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        """Make a Groq API call with retry logic.
        
        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            
        Returns:
            The Groq API response
            
        Raises:
            Exception: If the API call fails after all retries
        """
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
                
            self.logger.debug(f"Making Groq API call with messages: {json.dumps(messages, indent=2)}")
            response = self.groq_client.chat.completions.create(**kwargs)
            self.logger.debug("Received response from Groq API")
            return response
        except Exception as e:
            self.logger.error(f"Groq API call failed: {str(e)}")
            raise

    def _convert_tool_calls_to_dict(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Convert Groq tool calls to serializable dictionary format.
        
        Args:
            tool_calls: List of Groq tool call objects
            
        Returns:
            List of serializable tool call dictionaries
        """
        return [{
            "id": tool_call.id,
            "type": tool_call.type,
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments
            }
        } for tool_call in tool_calls]

    async def _execute_tool_call(self, tool_call: Any, messages: List[Dict[str, Any]]) -> Tuple[str, bool]:
        """Execute a single tool call and handle its result.
        
        Args:
            tool_call: The tool call object to execute
            messages: The current conversation messages
            
        Returns:
            Tuple of (result text, success status)
        """
        function_call = tool_call.function
        tool_name = function_call.name
        
        try:
            args = json.loads(function_call.arguments)
        except json.JSONDecodeError as e:
            return f"Error parsing arguments for {tool_name}: {str(e)}", False
        
        self.logger.debug(f"Calling tool {tool_name} with args {args}")
        
        try:
            result = await self.session.call_tool(tool_name, args)
            result_content = result.content
            if not isinstance(result_content, str):
                try:
                    result_content = json.dumps(result_content)
                except Exception as e:
                    result_content = str(result_content)
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_content
            })
            return f"[Tool {tool_name} result: {result_content}]", True
            
        except Exception as e:
            error_message = f"Error executing tool {tool_name}: {str(e)}"
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": error_message
            })
            return error_message, False

    async def _handle_tool_calls(self, assistant_message: Any, messages: List[Dict[str, Any]]) -> List[str]:
        """Handle all tool calls from an assistant message.
        
        Args:
            assistant_message: The assistant message containing tool calls
            messages: The current conversation messages
            
        Returns:
            List of result texts from tool executions
        """
        final_text = []
        
        # Convert tool calls to serializable format
        tool_calls = self._convert_tool_calls_to_dict(assistant_message.tool_calls)
        
        # Add assistant message with tool calls to conversation
        messages.append({
            "role": "assistant",
            "content": assistant_message.content if assistant_message.content else "",
            "tool_calls": tool_calls
        })
        
        # Execute each tool call
        for tool_call in assistant_message.tool_calls:
            result_text, _ = await self._execute_tool_call(tool_call, messages)
            final_text.append(result_text)
        
        return final_text

    async def _get_final_response(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Get the final response after tool executions.
        
        Args:
            messages: The current conversation messages
            
        Returns:
            The final response text or None if there was an error
        """
        try:
            final_response = await self._make_groq_api_call(messages)
            return final_response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error getting final response: {str(e)}")
            self.logger.debug(f"Messages sent to Groq: {json.dumps(messages, indent=2)}")
            return None

    async def process_query(self, query: str) -> str:
        """Process a query using Groq and available tools.
        
        Args:
            query: The user's query string
            
        Returns:
            The processed response including any tool outputs
            
        Raises:
            Exception: If there's an error processing the query or executing tools
        """
        messages = [{"role": "user", "content": query}]
        final_text = []

        try:
            # Get available tools from the server
            response = await self.session.list_tools()
            mcp_tools = response.tools
            groq_tools = self._convert_tool_schema(mcp_tools)

            # Initial Groq API call
            response = await self._make_groq_api_call(messages, groq_tools)
            assistant_message = response.choices[0].message
            
            # Add assistant's content if any
            if assistant_message.content:
                final_text.append(assistant_message.content)
            
            # Handle tool calls if any
            if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                tool_results = await self._handle_tool_calls(assistant_message, messages)
                final_text.extend(tool_results)
                
                # Get final response after tool executions
                final_response = await self._get_final_response(messages)
                if final_response:
                    final_text.append(final_response)
            
            return "\n".join(final_text)
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return f"Error processing query: {str(e)}"

    def _parse_command(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse a query to check if it's a command.
        
        Args:
            query: The input query string
            
        Returns:
            Tuple of (command, argument) if it's a command, (None, None) otherwise
        """
        if not query.startswith('/'):
            return None, None
            
        parts = query[1:].split(' ', 1)
        command = parts[0]
        argument = parts[1] if len(parts) > 1 else None
        return command, argument

    async def _handle_command(self, command: str, argument: Optional[str]) -> bool:
        """Handle a command and return whether to continue the chat loop.
        
        Args:
            command: The command to handle
            argument: Optional argument for the command
            
        Returns:
            True if the chat loop should continue, False otherwise
        """
        if command == 'quit':
            return False
        elif command == 'model':
            if not argument:
                self.logger.warning("No model specified. Usage: /model <model_name>")
                return True
            self.model = argument
            self.logger.info(f"Model changed to: {self.model}")
        elif command == 'help':
            self._print_help()
        elif command == 'clear':
            self._clear_history()
        else:
            self.logger.warning(f"Unknown command: {command}. Type /help for available commands.")
        return True

    def _print_help(self) -> None:
        """Print help information about available commands."""
        help_text = """
        Available commands:
        /help           - Show this help message
        /quit           - Exit the chat loop
        /model <name>   - Change the Groq model
        /clear          - Clear conversation history
        """
        print(help_text)

    def _clear_history(self) -> None:
        """Clear the conversation history."""
        self.messages = []
        self.logger.info("Conversation history cleared")

    async def chat_loop(self) -> None:
        """Run an interactive chat loop for processing user queries."""
        self.logger.info(f"Starting chat loop with model: {self.model}")
        print("\nWelcome to Groq MCP Client!")
        print("Type your queries or use /help to see available commands.")
        
        self.messages = []
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if not query:
                    continue
                
                # Check if it's a command
                command, argument = self._parse_command(query)
                if command:
                    if not await self._handle_command(command, argument):
                        break
                    continue
                
                # Process the query
                self.logger.debug(f"Processing query: {query}")
                response = await self.process_query(query)
                
                # Store in history
                self.messages.append({"role": "user", "content": query})
                self.messages.append({"role": "assistant", "content": response})
                
                # Display response
                print("\n" + response)
                    
            except KeyboardInterrupt:
                self.logger.info("Chat loop interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Error in chat loop: {str(e)}")
                print(f"\nError: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up resources and close connections."""
        await self.exit_stack.aclose()

async def main():
    """Main entry point for the application."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Check if a server script path was provided
    if len(sys.argv) < 2:
        logger.error("Usage: python groq_mcp_client.py <path_to_server_script>")
        sys.exit(1)
        
    # Create and run the client
    client = GroqMCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)
    finally:
        # Ensure resources are cleaned up
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())