"""Message tool for agent communication without execution."""

from typing import Dict, Any, Optional
from .base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation


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
    async def execute(self, message: str, category: str = "info", **kwargs) -> ToolResult:
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

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=formatted_message,
                metadata={
                    "category": category,
                    "raw_message": message,
                    "tool_type": "communication"
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to send message: {str(e)}",
                metadata={"tool_type": "communication"}
            )