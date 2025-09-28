"""Coding-focused agent implementation."""

from typing import Optional

from .base import Agent
from ..llm import completion
from ..runtime import Plan
from ..tools import BashTool, MessageTool, ReadTool, WriteTool, UpdateTool
from ..trace import trace_operation


class CodingAgent(Agent):
    """
    Experienced Software Engineer Agent

    An expert-level coding agent that embodies the practices of a senior software engineer
    with 10+ years of experience in modern software development. Follows industry best
    practices, emphasizes code quality, testing, security, and maintainability.
    """

    name = "coding_agent"
    description = """Senior Software Engineer specializing in high-quality software development.
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

    def __init__(self):
        super().__init__(
            name=self.name,
            description=self.description
        )

        # Register essential coding tools
        self.register_tools([
            BashTool(),
            MessageTool(),
            ReadTool(),
            WriteTool(),
            UpdateTool()
        ])

    @trace_operation
    async def review_plan(self, plan: Plan, task: str) -> Plan:
        """Review current plan state and update todo list based on completed steps."""
        system_prompt = self._build_system_prompt()

        # Distinguish between initial planning and ongoing review
        if not plan.completed and not plan.todo:
            # Initial planning - create first todo list
            user_message = f"""Task: {task}

This is a new task. Create an initial plan with the necessary steps."""
        else:
            # Ongoing review - review current state and update todos
            user_message = f"""Task: {task}

Current plan state:
{plan.to_json()}

Based on the completed steps and their results, provide an updated todo list.
If the task is complete, return an empty todo list with the final output.
If more steps are needed, specify them in the todo list."""

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


    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        tools_desc = self.get_tools_description(include_capabilities=True, include_use_cases=True, include_schema=True)
        json_format = self.get_json_format_instructions()

        return f"""You are a Senior Software Engineer with 10+ years of experience in enterprise software development.

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
1. Understand requirements thoroughly before coding
2. Read existing code to understand current structure
3. Design architecture and consider edge cases
4. Write tests first (TDD approach when applicable)
5. Create/update files with clean, readable code
6. Add comprehensive error handling
7. Document code and APIs appropriately
8. Run tests and ensure all pass
9. Perform code quality checks (linting, type checking)
10. Consider security implications and vulnerabilities
11. Optimize performance where needed

FILE OPERATIONS:
• Use 'read' tool to examine existing code before making changes
• Use 'write' tool to create new files with proper structure
• Use 'update' tool to modify existing files with precise patches
• Always review file contents after changes to ensure correctness

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
1. The original task
2. A list of completed steps and their results (if any)
3. The current todo list (if any)

Your job is to:
1. For new tasks: Create an initial todo list following best practices
2. For ongoing tasks: Review results and update the todo list
3. Ensure each step meets professional quality standards
4. Include testing and quality assurance steps
5. Consider security and performance implications
6. If the task is complete, provide comprehensive final output

Available tools:
{tools_desc}

{json_format}

EXECUTION REQUIREMENTS:
- Create concrete, actionable steps with specific tools and commands
- Include testing steps for any code changes
- Add code quality checks (linting, type checking) where applicable
- Consider error handling and edge cases in implementations
- Review results carefully and add corrective steps if needed
- Ensure all code follows industry best practices
- Document any architectural decisions or trade-offs
- If the task is complete, provide detailed summary of accomplishments

Remember: You are building production-quality software that will be maintained by other engineers."""


