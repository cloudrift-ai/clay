"""Console tools for agent communication and user interaction."""

from typing import Dict, Any, Optional
from datetime import datetime
from .base import Tool, ToolResult, ToolError
from ..trace import trace_operation


class AgentMessageToolResult(ToolResult):
    """Specific result class for MessageTool."""

    def get_formatted_output(self) -> str:
        """Get formatted output for Claude Code style display."""
        if self.output:
            # Remove the emoji prefix for cleaner display
            output = self.output
            if output.startswith("💬 "):
                output = output[2:]
            elif output.startswith("📋 Summary: "):
                output = output[11:]
            elif output.startswith("💡 Explanation: "):
                output = output[15:]
            elif output.startswith("ℹ️ Status: "):
                output = output[10:]
            elif output.startswith("⚠️ Warning: "):
                output = f"Warning: {output[11:]}"
            elif output.startswith("❌ Error: "):
                output = f"Error: {output[9:]}"
            return output
        else:
            return f"Error: {self.error or 'Message delivery failed'}"


class AgentMessageTool(Tool):
    """Tool for agents to communicate messages, summaries, or explanations to users."""

    def __init__(self):
        super().__init__(
            name="message",
            description="Communicate information, explanations, or status updates to the user without executing any actions",
            capabilities=[
                "Display messages to the user",
                "Provide explanations of what was done",
                "Share analysis or findings",
                "Communicate status updates",
                "Explain reasoning or decisions",
                "Summarize results"
            ],
            use_cases=[
                "Explaining what steps were completed",
                "Providing analysis of results",
                "Communicating errors or issues",
                "Sharing intermediate findings",
                "Explaining next steps or reasoning",
                "Summarizing the overall progress"
            ]
        )

    def get_tool_call_display(self, parameters: Dict[str, Any]) -> str:
        """Get formatted display for message tool invocation."""
        message = parameters.get('message', '')
        if len(message) > 60:
            message = message[:57] + "..."
        return f"⏺ Message({message})"

    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to communicate to the user"
                },
                "category": {
                    "type": "string",
                    "enum": ["info", "summary", "explanation", "status", "warning", "error"],
                    "description": "Category of the message for appropriate formatting",
                    "default": "info"
                }
            },
            "required": ["message"]
        }

    @trace_operation
    async def execute(self, message: str, category: str = "info", **kwargs) -> AgentMessageToolResult:
        """Display a message to the user.

        Args:
            message: The message to display
            category: Category of message (info, summary, explanation, status, warning, error)
            **kwargs: Additional parameters (ignored)

        Returns:
            ToolResult with the message content
        """
        try:
            # Validate category
            valid_categories = ["info", "summary", "explanation", "status", "warning", "error"]
            if category not in valid_categories:
                category = "info"

            # Format message based on category
            if category == "summary":
                formatted_message = f"📋 Summary: {message}"
            elif category == "explanation":
                formatted_message = f"💡 Explanation: {message}"
            elif category == "status":
                formatted_message = f"ℹ️ Status: {message}"
            elif category == "warning":
                formatted_message = f"⚠️ Warning: {message}"
            elif category == "error":
                formatted_message = f"❌ Error: {message}"
            else:  # info
                formatted_message = f"💬 {message}"

            return AgentMessageToolResult(
                                output=formatted_message,
                metadata={
                    "category": category,
                    "raw_message": message,
                    "tool_type": "communication"
                }
            )

        except Exception as e:
            raise ToolError(f"Failed to send message: {str(e)}")


class UserMessageToolResult(ToolResult):
    """Specific result class for UserMessageTool."""

    def get_formatted_output(self) -> str:
        """Get formatted output for Claude Code style display."""
        if self.output:
            return f"User message: {self.output}"
        else:
            return f"Error: {self.error or 'Failed to process user message'}"


class UserMessageTool(Tool):
    """Tool for encoding the initial user prompt/message to the agent."""

    def __init__(self):
        super().__init__(
            name="user_message",
            description="Encodes the user's initial prompt or message to the agent",
            capabilities=[
                "Capture the user's initial request",
                "Store the user's instructions",
                "Provide context for the agent's task",
                "Record the starting point of the conversation"
            ],
            use_cases=[
                "At the beginning of every agent task",
                "To record what the user asked for",
                "To provide context for subsequent operations",
                "To maintain a record of the user's instructions"
            ]
        )

    def get_tool_call_display(self, parameters: Dict[str, Any]) -> str:
        """Get formatted display for user message tool invocation."""
        message = parameters.get('message', '')
        if len(message) > 60:
            message = message[:57] + "..."
        return f"⏺ UserMessage({message})"

    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The user's prompt or message to the agent"
                }
            },
            "required": ["message"]
        }

    @trace_operation
    async def execute(self, message: str, **kwargs) -> UserMessageToolResult:
        """Process and store the user's message.

        Args:
            message: The user's prompt or instructions
            **kwargs: Additional parameters (ignored)

        Returns:
            UserMessageToolResult with the processed message
        """
        try:
            # Simply encode and return the user's message
            # This tool doesn't ask for input, it just records what was provided
            return UserMessageToolResult(
                output=message,
                metadata={
                    "message": message,
                    "tool_type": "user_context",
                    "timestamp": datetime.now().isoformat()
                }
            )

        except Exception as e:
            raise ToolError(f"Failed to process user message: {str(e)}")


class UserInputToolResult(ToolResult):
    """Specific result class for UserInputTool."""

    def get_formatted_output(self) -> str:
        """Get formatted display for user input."""
        if self.output:
            return f"User input: {self.output}"
        else:
            return f"Error: {self.error or 'Failed to get user input'}"


class UserInputTool(Tool):
    """Tool for prompting and capturing interactive user input during execution."""

    def __init__(self):
        super().__init__(
            name="user_input",
            description="Prompt the user for input during execution and capture their response",
            capabilities=[
                "Prompt user for additional instructions",
                "Get user clarification during execution",
                "Capture user decisions or preferences",
                "Allow user to provide additional context",
                "Enable interactive communication during task execution"
            ],
            use_cases=[
                "When agent needs clarification from user",
                "To get user approval before proceeding",
                "To ask for additional requirements",
                "To let user guide the next steps",
                "When encountering ambiguous situations",
                "To confirm user preferences or decisions"
            ]
        )

    def get_tool_call_display(self, parameters: Dict[str, Any]) -> str:
        """Get formatted display for user input tool invocation."""
        prompt = parameters.get('prompt', 'Enter input')
        if len(prompt) > 40:
            prompt = prompt[:37] + "..."
        return f"⏺ UserInput({prompt})"

    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt message to show the user",
                    "default": "Please provide your input:"
                },
                "context": {
                    "type": "string",
                    "description": "Additional context about why input is needed",
                    "default": ""
                }
            },
            "required": ["prompt"]
        }

    @trace_operation
    async def execute(self, prompt: str = "Please provide your input:", context: str = "", **kwargs) -> UserInputToolResult:
        """Prompt the user for input and capture their response.

        Args:
            prompt: The prompt message to show the user
            context: Additional context about why input is needed
            **kwargs: Additional parameters (ignored)

        Returns:
            UserInputToolResult with the user's input
        """
        try:
            # Import here to avoid circular imports
            import sys

            # Clear any previous output and show the prompt
            if context:
                print(f"\n{context}")

            # Display the input prompt
            print(f"\n{prompt}")
            print("─" * 100)

            # Get user input
            try:
                user_input = input("> ").strip()
            except KeyboardInterrupt:
                user_input = ""
                print("\n[User cancelled input]")
            except EOFError:
                user_input = ""
                print("\n[End of input]")

            print("─" * 100)

            # Return the user's input
            return UserInputToolResult(
                output=user_input,
                metadata={
                    "prompt": prompt,
                    "context": context,
                    "tool_type": "interactive_input",
                    "timestamp": datetime.now().isoformat(),
                    "user_cancelled": user_input == "" and context != ""
                }
            )

        except Exception as e:
            raise ToolError(f"Failed to get user input: {str(e)}")