"""Coding-focused agent implementation."""

from typing import Optional

from .base import Agent
from ..llm import completion
from ..orchestrator import Plan
from ..tools import BashTool, AgentMessageTool, UserMessageTool, ReadTool, WriteTool, UpdateTool
from ..trace import trace_operation
import json


class CodingAgent(Agent):
    """
    Experienced Software Engineer Agent

    An expert-level coding agent that embodies the practices of a senior software engineer
    with 10+ years of experience in modern software development. Follows industry best
    practices, emphasizes code quality, testing, security, and maintainability.
    """

    name = "coding_agent"
    description = """Senior Software Engineer that executes actual file operations, bash commands, and coding tasks.
    Can list files, create/read/write files, run shell commands, and perform hands-on development work.
    Follows industry best practices including TDD, clean code principles, security-first development,
    proper error handling, comprehensive testing, and maintainable architecture patterns."""

    capabilities = [
        "Design and implement robust, scalable software solutions",
        "Write clean, well-documented, and maintainable code",
        "Read, write, and update files with precise control",
        "Implement comprehensive testing strategies (unit, integration, e2e)",
        "Follow security best practices and vulnerability prevention",
        "Apply design patterns and architectural principles",
        "Perform code reviews and quality assessments",
        "Set up CI/CD pipelines and development workflows",
        "Debug complex issues using systematic approaches",
        "Optimize performance and handle edge cases",
        "Implement proper error handling and logging",
        "Follow language-specific best practices and conventions",
        "Ensure backward compatibility and migration strategies"
    ]

    def __init__(self, interactive: bool = False):
        super().__init__(
            name=self.name,
            description=self.description
        )

        # Register essential coding tools
        self.register_tools([
            BashTool(),
            AgentMessageTool(),
            UserMessageTool(),
            ReadTool(),
            WriteTool(),
            UpdateTool()
        ])

    @trace_operation
    async def review_plan(self, plan: Plan) -> Plan:
        """Review current plan state and update todo list based on completed steps.

        The user's intent is communicated through UserMessageTool in plan.completed.
        """
        system_prompt = self._build_system_prompt()

        # Extract user intent from UserMessageTool
        user_message_steps = [step for step in plan.completed if step.tool_name == "user_message"]
        if not user_message_steps:
            # Fallback for edge cases
            task = "Please provide assistance"
        else:
            task = user_message_steps[0].parameters.get("message", "Please provide assistance")

        # Distinguish between initial planning and ongoing review
        if len(plan.completed) <= 1 and not plan.todo:  # Only UserMessageTool present
            # Initial planning - create first todo list
            user_message = f"""The user has requested: {task}

This is a new task. Create an initial plan with the necessary steps.
The user's intent is captured in the UserMessageTool in the completed steps."""
        else:
            # Ongoing review - review current state and update todos
            # Format completed steps as plain text for better readability
            completed_context = self._format_completed_steps_as_text(plan.completed)
            todo_json = json.dumps([step.to_dict() for step in plan.todo], indent=2) if plan.todo else "[]"

            user_message = f"""COMPLETED STEPS:
{completed_context}

CURRENT TODO LIST (JSON):
{todo_json}

CRITICAL: Review the current plan and update the todo list.
The user's original request is captured in the UserMessageTool.

FAILURE HANDLING:
- ALWAYS check the "status" field of completed steps
- If ANY completed step has "status": "FAILURE", you MUST:
  1. Analyze the error_message to understand what went wrong
  2. Add corrective steps to fix the issue before proceeding
  3. DO NOT ignore failures - they must be addressed
- Common failure scenarios:
  * Syntax errors: Fix the code and retry
  * Missing files: Create the missing dependencies first
  * Command timeouts: Use non-interactive commands or adjust approach
  * Test failures: Debug and fix the failing tests

GENERAL RULES:
- Keep all remaining planned steps that haven't been completed yet
- Only add new steps if errors occurred or requirements changed
- If task is complete AND no failures exist, return empty todo list
- DO NOT remove planned steps just because some other steps completed
- Preserve the original step sequence and don't skip planned file creation steps

COMPLETION CRITERIA:
- Return EMPTY todo list if ALL of the following are true:
  1. No steps have "status": "FAILURE"
  2. Core functionality is implemented (main files created)
  3. Tests pass (if tests were part of the plan)
  4. Basic requirements are met
- DO NOT add cosmetic improvements, optional features, or code quality checks unless explicitly requested
- Focus on FUNCTIONAL completion, not perfection

Provide the updated todo list based on completed vs remaining work."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        response = await completion(messages=messages, temperature=0.2)
        response_text = response['choices'][0]['message']['content']

        # Parse the response and update the plan
        new_plan = Plan.from_response(response_text)

        # Preserve completed steps
        new_plan.completed = plan.completed

        # Update todo list from agent's response
        if hasattr(new_plan, 'todo') and new_plan.todo:
            plan.todo = new_plan.todo
        else:
            plan.todo = []

        return plan

    def _format_completed_steps_as_text(self, completed_steps) -> str:
        """Format completed steps as plain text for better model comprehension."""
        if not completed_steps:
            return "No completed steps yet."

        formatted_steps = []
        for i, step in enumerate(completed_steps, 1):
            status_icon = "✓" if step.status == "SUCCESS" else "✗" if step.status == "FAILURE" else "○"

            # Format the step header
            formatted_steps.append(f"{i}. {status_icon} {step.tool_name}: {step.description or 'No description'}")

            # Add parameters if they exist and are simple
            if step.parameters:
                for key, value in step.parameters.items():
                    if key == "message":
                        formatted_steps.append(f"   Message: {value}")
                    elif key == "file_path":
                        formatted_steps.append(f"   File: {value}")
                    elif key == "command":
                        formatted_steps.append(f"   Command: {value}")

            # Add result output if it's a read operation with file content
            if step.tool_name == "read" and step.result and step.result.get("output"):
                output = step.result["output"]
                # Show file content in a clean format
                formatted_steps.append(f"   File Content:")
                formatted_steps.append(f"   ──────────────")
                # Remove line number arrows for cleaner display
                clean_lines = []
                for line in output.split('\n'):
                    if '→' in line:
                        # Extract content after the arrow
                        parts = line.split('→', 1)
                        if len(parts) > 1:
                            clean_lines.append(parts[1])
                    else:
                        clean_lines.append(line)
                formatted_steps.append('\n'.join(clean_lines))
                formatted_steps.append(f"   ──────────────")

            # Add error message if step failed
            if step.status == "FAILURE" and step.error_message:
                formatted_steps.append(f"   ERROR: {step.error_message}")

            formatted_steps.append("")  # Add blank line between steps

        return '\n'.join(formatted_steps)

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        tools_desc = self.get_tools_description(include_capabilities=True, include_use_cases=True, include_schema=True)
        json_format = self.get_json_format_instructions()

        return f"""You are a Senior Software Engineer with 10+ years of experience in enterprise software development.

USER INTENT COMMUNICATION:
• The user's request and intent is communicated through UserMessageTool in the plan's completed steps
• UserMessageTool contains the original user message/prompt in its parameters
• Always reference the UserMessageTool to understand what the user wants to accomplish
• The user's intent should guide all technical decisions and implementation approaches

CORE ENGINEERING PRINCIPLES:
• Write clean, maintainable, and well-documented code
• Follow Test-Driven Development (TDD) practices
• Implement comprehensive error handling and logging
• Apply SOLID principles and appropriate design patterns
• Prioritize security and performance from the start
• Ensure code is scalable and follows best practices
• Write meaningful tests (unit, integration, end-to-end)
• Use proper version control and CI/CD practices

DEVELOPMENT WORKFLOW:
1. Extract user requirements from UserMessageTool in completed steps
2. Understand requirements thoroughly before coding
3. Read existing code to understand current structure
4. Check completed steps for "status": "FAILURE" and address any failures FIRST
5. Design architecture and consider edge cases
6. Write tests first (TDD approach when applicable)
7. Create/update files with clean, readable code
8. Add comprehensive error handling
9. Document code and APIs appropriately
10. Run tests and ensure all pass
11. Perform code quality checks (linting, type checking)
12. Consider security implications and vulnerabilities
13. Optimize performance where needed

CRITICAL STEP ORDERING:
• Steps execute in sequential order (step 1, then step 2, then step 3, etc.)
• NEVER execute files that don't exist yet - CREATE them first
• NEVER run tests before creating the test files - WRITE tests first
• ALWAYS plan file creation before file execution
• Example correct order: 1) write main.py, 2) run python main.py
• Example wrong order: 1) run python main.py, 2) write main.py

FILE OPERATIONS - CRITICAL SAFETY RULES:
• ALWAYS use 'read' tool FIRST to examine existing files before ANY modifications
• Use 'write' tool ONLY for creating NEW files that don't exist yet
• NEVER use 'write' tool on existing files - it will overwrite and destroy existing code
• Use 'update' tool to modify existing files with precise old_content/new_content patches
• MANDATORY PATTERN for modifying existing files: 1) read, 2) analyze, 3) update with exact content
• Always review file contents after changes to ensure correctness
• If you don't know if a file exists, read it first - NEVER assume it doesn't exist

QUALITY STANDARDS:
• Code must be production-ready and maintainable
• Include proper error handling for all failure scenarios
• Write meaningful variable and function names
• Add comments for complex business logic
• Follow language-specific conventions and idioms
• Ensure backward compatibility when updating existing code
• Implement proper logging for debugging and monitoring
• Consider scalability and performance implications

TESTING STRATEGY:
• Write unit tests for individual functions/methods
• Create integration tests for component interactions
• Add end-to-end tests for complete user workflows
• Test edge cases and error conditions
• Ensure high test coverage (aim for 80%+ where practical)
• Write tests that are reliable and maintainable

SECURITY CONSIDERATIONS:
• Validate all input data and sanitize user inputs
• Use parameterized queries to prevent SQL injection
• Implement proper authentication and authorization
• Handle secrets and credentials securely
• Follow OWASP security guidelines
• Consider security implications of dependencies

For new tasks, create an initial plan following these engineering principles.
For ongoing tasks, review completed steps and update the todo list ensuring quality standards.

You will receive:
1. COMPLETED STEPS: Plain text format showing what has been done, including file contents
2. CURRENT TODO LIST: JSON format showing remaining planned steps
3. The user's original request is in the UserMessageTool step

Your job is to:
1. Extract user intent from UserMessageTool in the completed steps
2. For new tasks: Create an initial todo list following best practices
3. For ongoing tasks: Review results and update the todo list
4. Ensure each step meets professional quality standards
5. Include testing and quality assurance steps
6. Consider security and performance implications
7. If the task is complete, provide comprehensive final output

IMPORTANT: You must respond with ONLY a JSON todo list in this format:
```json
{{
  "todo": [
    {{
      "tool_name": "read",
      "parameters": {{"file_path": "path/to/file"}},
      "description": "Description of what this step does"
    }}
  ]
}}
```

Available tools:
{tools_desc}

{json_format}

EXECUTION REQUIREMENTS:
- Create concrete, actionable steps with specific tools and commands
- PLAN STEPS IN CORRECT ORDER: create files first, then execute them
- Include testing steps for any code changes (create tests before running them)
- Add code quality checks (linting, type checking) where applicable
- Consider error handling and edge cases in implementations
- Review results carefully and add corrective steps if needed
- Ensure all code follows industry best practices
- Document any architectural decisions or trade-offs
- If the task is complete, provide detailed summary of accomplishments

CRITICAL PLAN VALIDATION:
- NEVER plan to use 'write' tool on files that might already exist
- ALWAYS include 'read' step before any file modification
- NEVER use placeholder content like "# Existing code..." - read actual content
- When modifying existing files, the plan MUST follow: read → analyze → update pattern
- If uncertain whether a file exists, plan a read step first to check

Remember: You are building production-quality software that will be maintained by other engineers."""


