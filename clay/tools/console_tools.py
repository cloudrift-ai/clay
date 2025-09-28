"""Console tools for agent communication and user interaction."""

from typing import Dict, Any, Optional
from .base import Tool, ToolResult, ToolError
from ..trace import trace_operation


class MessageToolResult(ToolResult):
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


class MessageTool(Tool):
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
    async def execute(self, message: str, category: str = "info", **kwargs) -> MessageToolResult:
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

            return MessageToolResult(
                                output=formatted_message,
                metadata={
                    "category": category,
                    "raw_message": message,
                    "tool_type": "communication"
                }
            )

        except Exception as e:
            raise ToolError(f"Failed to send message: {str(e)}")


class UserInputToolResult(ToolResult):
    """Specific result class for UserInputTool."""

    def get_formatted_output(self) -> str:
        """Get formatted output for Claude Code style display."""
        if self.output:
            return f"User response: {self.output}"
        else:
            return f"Error: {self.error or 'Failed to get user input'}"


class UserInputTool(Tool):
    """Tool for requesting input from the user during execution."""

    def __init__(self):
        super().__init__(
            name="user_input",
            description="Request input or clarification from the user during task execution",
            capabilities=[
                "Ask the user for additional information",
                "Request clarification on requirements",
                "Get user preferences or choices",
                "Confirm actions with the user",
                "Gather missing parameters"
            ],
            use_cases=[
                "When task requirements are ambiguous",
                "When user preferences are needed",
                "When critical decisions require confirmation",
                "When additional context is required",
                "When choosing between multiple valid options"
            ]
        )

    def get_tool_call_display(self, parameters: Dict[str, Any]) -> str:
        """Get formatted display for user input tool invocation."""
        prompt = parameters.get('prompt', '')
        if len(prompt) > 60:
            prompt = prompt[:57] + "..."
        return f"⏺ UserInput({prompt})"

    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The question or prompt to display to the user"
                },
                "default": {
                    "type": "string",
                    "description": "Optional default value if user provides no input"
                },
                "choices": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of valid choices to present to the user"
                }
            },
            "required": ["prompt"]
        }

    @trace_operation
    async def execute(self, prompt: str, default: Optional[str] = None, choices: Optional[list] = None, **kwargs) -> UserInputToolResult:
        """Request input from the user.

        Args:
            prompt: The question or prompt to display
            default: Optional default value
            choices: Optional list of valid choices
            **kwargs: Additional parameters (ignored)

        Returns:
            UserInputToolResult with the user's response
        """
        try:
            # Format the prompt for display
            formatted_prompt = f"\n❓ {prompt}"

            if choices:
                formatted_prompt += f"\n   Options: {', '.join(choices)}"

            if default:
                formatted_prompt += f"\n   (default: {default})"

            formatted_prompt += "\n   > "

            # Get user input (synchronously, as input() blocks)
            user_response = input(formatted_prompt)

            # Use default if no input provided
            if not user_response and default:
                user_response = default

            # Validate against choices if provided
            if choices and user_response not in choices:
                raise ToolError(f"Invalid choice. Please select from: {', '.join(choices)}")

            return UserInputToolResult(
                output=user_response,
                metadata={
                    "prompt": prompt,
                    "response": user_response,
                    "tool_type": "interaction"
                }
            )

        except KeyboardInterrupt:
            raise ToolError("User cancelled input")
        except Exception as e:
            raise ToolError(f"Failed to get user input: {str(e)}")