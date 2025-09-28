"""Message tool for agent communication without execution."""

from typing import Dict, Any, Optional
from .base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation


class MessageToolResult(ToolResult):
    """Specific result class for MessageTool."""

    def get_formatted_output(self) -> str:
        """Get formatted output for Claude Code style display."""
        if self.status == ToolStatus.SUCCESS and self.output:
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
                status=ToolStatus.SUCCESS,
                output=formatted_message,
                metadata={
                    "category": category,
                    "raw_message": message,
                    "tool_type": "communication"
                }
            )

        except Exception as e:
            return MessageToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to send message: {str(e)}",
                metadata={"tool_type": "communication"}
            )