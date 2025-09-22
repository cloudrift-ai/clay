"""CLI interface for Clay."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from .agents import (
    CodingAgent, ResearchAgent, FastCodingAgent,
    AgentOrchestrator, AgentContext, StreamingAgent, ProgressiveSession
)
from .tools import (
    ReadTool, WriteTool, EditTool, GlobTool,
    BashTool, GrepTool, SearchTool,
    WebFetchTool, WebSearchTool
)
from .llm import create_llm_provider, get_default_provider
from .conversation import ConversationManager
from .session_manager import SessionManager
from .orchestrator import ClayOrchestrator, PolicyConfig


console = Console()


class ClaySession:
    """Main session handler for Clay CLI."""

    def __init__(self, llm_provider=None, working_dir: str = ".", fast_mode: bool = False, session_id: Optional[str] = None,
                 use_orchestrator: bool = True):
        self.llm_provider = llm_provider or get_default_provider()
        self.working_dir = Path(working_dir).resolve()
        self.fast_mode = fast_mode
        self.use_orchestrator = use_orchestrator

        # Initialize both orchestrators
        self.agent_orchestrator = AgentOrchestrator()
        self.clay_orchestrator = None

        self.conversation = ConversationManager()
        self.session_manager = SessionManager()

        # Session management
        self.session_id = session_id or self.session_manager.create_session()

        # New Claude Code compatible options
        self.allowed_tools = None
        self.disallowed_tools = None
        self.max_turns = None
        self.verbose = False
        self.append_system_prompt = None

        self.setup_agents()

        # Initialize Clay orchestrator if requested
        if self.use_orchestrator and self.llm_provider:
            try:
                self.setup_clay_orchestrator()
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to initialize Clay orchestrator: {e}[/yellow]")
                console.print("[yellow]Falling back to legacy agent system[/yellow]")
                self.use_orchestrator = False

    def load_session(self, session_id: str) -> bool:
        """Load a previous session."""
        session_data = self.session_manager.get_session(session_id)
        if session_data:
            self.session_id = session_id
            # Restore conversation history
            for message in session_data["messages"]:
                if message["role"] == "user":
                    self.conversation.add_user_message(message["content"])
                elif message["role"] == "assistant":
                    self.conversation.add_assistant_message(message["content"])
            return True
        return False

    def setup_agents(self):
        """Initialize and configure agents."""
        if self.fast_mode:
            coding_agent = FastCodingAgent(self.llm_provider)
        else:
            coding_agent = CodingAgent(self.llm_provider)

        coding_agent.register_tools([
            ReadTool(),
            WriteTool(),
            EditTool(),
            GlobTool(),
            BashTool(),
            GrepTool(),
            SearchTool()
        ])

        research_agent = ResearchAgent(self.llm_provider)
        research_agent.register_tools([
            GrepTool(),
            SearchTool(),
            WebFetchTool(),
            WebSearchTool()
        ])

        self.agent_orchestrator.register_agent(coding_agent)
        self.agent_orchestrator.register_agent(research_agent)

        # Store the primary coding agent for orchestrator use
        self.primary_agent = coding_agent

    def setup_clay_orchestrator(self):
        """Initialize the Clay orchestrator with all components."""
        # Create policy configuration
        policy_config = PolicyConfig(
            # Allow common paths but restrict sensitive ones
            denied_paths=[
                ".env*", "*.key", "*.pem", "*.cert",
                ".ssh/*", ".aws/*", ".gcp/*"
            ],
            # Security restrictions
            forbid_credentials=True,
            forbid_telemetry=True,
            forbid_license_changes=True,
            # Size limits
            max_file_size=1_000_000,  # 1MB
            max_diff_size=10_000,     # 10k lines
            max_files_changed=50
        )

        self.clay_orchestrator = ClayOrchestrator(
            agent=self.primary_agent,
            working_dir=self.working_dir,
            policy_config=policy_config
        )

    async def process_message(self, message: str) -> str:
        """Process a user message and return response."""
        self.conversation.add_user_message(message)
        self.session_manager.add_message(self.session_id, "user", message)

        # Check if this is a complex coding task that should use the orchestrator
        if self.use_orchestrator and self.clay_orchestrator and self._is_complex_task(message):
            return await self._process_with_orchestrator(message)
        else:
            return await self._process_with_agents(message)

    def _is_complex_task(self, message: str) -> bool:
        """Determine if this is a complex coding task that benefits from the orchestrator."""
        complex_indicators = [
            "implement", "create", "build", "add", "modify", "refactor",
            "fix", "debug", "update", "write code", "change", "develop"
        ]

        simple_indicators = [
            "read", "show", "find", "search", "grep", "list",
            "what is", "how many", "explain", "describe"
        ]

        message_lower = message.lower()

        # If it's clearly a simple query, use agents
        if any(indicator in message_lower for indicator in simple_indicators):
            return False

        # If it mentions files or code changes, use orchestrator
        if any(indicator in message_lower for indicator in complex_indicators):
            return True

        # Default to agents for ambiguous cases
        return False

    async def _process_with_orchestrator(self, message: str) -> str:
        """Process message using the Clay orchestrator."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing with Clay orchestrator...", total=None)

            try:
                # Extract constraints from message if any
                constraints = {}
                if self.append_system_prompt:
                    constraints["system_prompt"] = self.append_system_prompt

                result = await self.clay_orchestrator.process_task(message, constraints)

                progress.update(task, completed=True)

                # Format response based on result
                if result.get("status") == "success":
                    response = self._format_orchestrator_success(result)
                elif result.get("status") == "error":
                    response = f"Error: {result.get('error', 'Unknown error occurred')}"
                else:
                    response = f"Task completed with status: {result.get('status', 'unknown')}"

            except Exception as e:
                progress.update(task, completed=True)
                response = f"Orchestrator error: {str(e)}"

        self.conversation.add_assistant_message(response)
        self.session_manager.add_message(self.session_id, "assistant", response)
        return response

    async def _process_with_agents(self, message: str) -> str:
        """Process message using the legacy agent system."""
        context = AgentContext(
            working_directory=str(self.working_dir),
            conversation_history=self.conversation.get_history(),
            available_tools=[],
            metadata={}
        )

        # Add system prompt if specified
        if self.append_system_prompt:
            context.metadata["append_system_prompt"] = self.append_system_prompt

        agent_name = self.determine_agent(message)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Thinking with {agent_name}...", total=None)

            task_id = f"task_{len(self.agent_orchestrator.tasks)}"
            agent_task = self.agent_orchestrator.create_task(
                task_id=task_id,
                prompt=message,
                agent_name=agent_name
            )

            await self.agent_orchestrator.submit_task(agent_task)
            result = await self.agent_orchestrator.run_task(agent_task, context)

            progress.update(task, completed=True)

        if result.error:
            response = f"Error: {result.error}"
        else:
            response = result.output or "Task completed"

        self.conversation.add_assistant_message(response)
        self.session_manager.add_message(self.session_id, "assistant", response)
        return response

    def _format_orchestrator_success(self, result: dict) -> str:
        """Format successful orchestrator result into readable response."""
        lines = []

        # Basic completion message
        lines.append("✅ Task completed successfully!")

        # Add duration info
        duration = result.get("duration", 0)
        if duration > 0:
            lines.append(f"⏱️  Duration: {duration:.1f} seconds")

        # Add retry info if any
        retry_count = result.get("retry_count", 0)
        if retry_count > 0:
            lines.append(f"🔄 Retries: {retry_count}")

        # Add artifacts summary
        artifacts = result.get("artifacts", {})
        if artifacts:
            lines.append("\n📋 Summary:")

            if "plan" in artifacts:
                plan = artifacts["plan"]
                step_count = len(plan.get("steps", []))
                lines.append(f"  • Created plan with {step_count} steps")

            if "diffs" in artifacts and artifacts["diffs"]:
                diff_count = len(artifacts["diffs"])
                lines.append(f"  • Applied {diff_count} patch(es)")

            if "full_test_results" in artifacts:
                test_results = artifacts["full_test_results"]
                if test_results.get("passed"):
                    lines.append("  • ✅ All tests passing")
                else:
                    failed = len(test_results.get("failures", []))
                    lines.append(f"  • ❌ {failed} test(s) failing")

            if "format_lint_results" in artifacts:
                format_lint = artifacts["format_lint_results"]
                if artifacts.get("format_lint_clean"):
                    lines.append("  • ✅ Format and lint checks passed")
                else:
                    lines.append("  • ⚠️  Format/lint issues detected")

        # Add state information
        final_state = result.get("final_state")
        if final_state and final_state != "DONE":
            lines.append(f"\n⚠️  Final state: {final_state}")

        return "\n".join(lines)

    def determine_agent(self, message: str) -> str:
        """Determine which agent to use based on message."""
        message_lower = message.lower()

        research_keywords = ["search", "find", "research", "look for", "grep", "analyze"]
        if any(keyword in message_lower for keyword in research_keywords):
            return "research_agent"

        return "coding_agent"


@click.command()
@click.argument("query", required=False)
@click.option("--print", "-p", is_flag=True, help="Print response without interactive mode")
@click.option("--provider", help="LLM provider (openai/anthropic/cloudrift)")
@click.option("--model", help="Model to use")
@click.option("--api-key", help="API key for provider")
@click.option("--fast", is_flag=True, help="Use fast mode for better performance")
@click.option("--add-dir", multiple=True, help="Add working directories")
@click.option("--allowed-tools", multiple=True, help="Specify allowed tools")
@click.option("--disallowed-tools", multiple=True, help="Specify disallowed tools")
@click.option("--output-format", type=click.Choice(["text", "json", "stream-json"]), default="text", help="Output format")
@click.option("--input-format", type=click.Choice(["text", "json"]), default="text", help="Input format")
@click.option("--verbose", is_flag=True, help="Enable detailed logging")
@click.option("--max-turns", type=int, help="Limit agentic turns")
@click.option("--continue", "-c", "continue_session", is_flag=True, help="Continue most recent conversation")
@click.option("--resume", "-r", help="Resume specific session by ID")
@click.option("--append-system-prompt", help="Append to system prompt")
@click.option("--use-orchestrator/--no-orchestrator", default=True, help="Use Clay orchestrator for complex tasks")
@click.option("--analyze-only", is_flag=True, help="Analyze project without making changes")
def cli(query: Optional[str], print: bool, provider: Optional[str], model: Optional[str],
        api_key: Optional[str], fast: bool, add_dir: tuple, allowed_tools: tuple,
        disallowed_tools: tuple, output_format: str, input_format: str, verbose: bool,
        max_turns: Optional[int], continue_session: bool, resume: Optional[str],
        append_system_prompt: Optional[str], use_orchestrator: bool, analyze_only: bool):
    """Clay - Agentic Coding System similar to Claude Code."""

    # Handle piped input
    piped_input = None
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()

    # Setup LLM provider
    llm_provider = None
    if provider:
        try:
            llm_provider = create_llm_provider(provider, api_key, model)
            if verbose:
                console.print(f"[green]Using {provider} provider with model {model or 'default'}[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: {e}[/yellow]")
            console.print("[yellow]Running without LLM provider (mock mode)[/yellow]")

    # Setup working directories
    working_dirs = list(add_dir) if add_dir else ["."]
    for dir_path in working_dirs:
        if not Path(dir_path).exists():
            console.print(f"[red]Error: Directory '{dir_path}' does not exist[/red]")
            sys.exit(1)

    # Create session with configuration
    session = ClaySession(
        llm_provider,
        working_dir=working_dirs[0],  # Primary working directory
        fast_mode=fast,
        use_orchestrator=use_orchestrator
    )

    # Configure session with additional options
    session.allowed_tools = set(allowed_tools) if allowed_tools else None
    session.disallowed_tools = set(disallowed_tools) if disallowed_tools else None
    session.max_turns = max_turns
    session.verbose = verbose
    session.append_system_prompt = append_system_prompt

    # Handle different execution modes
    if analyze_only:
        # Analysis mode - analyze project structure
        asyncio.run(run_analysis_mode(session, output_format))
    elif print or query or piped_input:
        # Headless mode - print response and exit
        asyncio.run(run_headless_mode(session, query, piped_input, output_format))
    elif continue_session:
        # Continue most recent conversation
        asyncio.run(run_continue_mode(session))
    elif resume:
        # Resume specific session
        asyncio.run(run_resume_mode(session, resume))
    else:
        # Interactive mode
        if not query:
            console.print(Panel.fit(
                "[bold cyan]Clay - Agentic Coding System[/bold cyan]\n"
                "Type 'help' for commands, 'exit' to quit",
                border_style="cyan"
            ))
        asyncio.run(run_interactive_mode(session, query))


async def run_analysis_mode(session: ClaySession, output_format: str):
    """Run in analysis mode - analyze project structure without changes."""
    import json

    if session.use_orchestrator and session.clay_orchestrator:
        console.print("[cyan]Analyzing project with Clay orchestrator...[/cyan]")
        result = await session.clay_orchestrator.analyze_project()
    else:
        console.print("[yellow]Orchestrator not available, using basic analysis[/yellow]")
        result = {"status": "error", "error": "Orchestrator not initialized"}

    if output_format == "json":
        console.print(json.dumps(result, indent=2))
    else:
        if result.get("status") == "success":
            console.print("[green]✅ Project Analysis Complete[/green]\n")

            stack_info = result.get("stack_info", {})
            if stack_info:
                console.print("[bold]📚 Technology Stack:[/bold]")
                for category, items in stack_info.items():
                    if items:
                        console.print(f"  {category}: {', '.join(items)}")

            stats = result.get("stats", {})
            if stats:
                console.print(f"\n[bold]📊 Project Statistics:[/bold]")
                for key, value in stats.items():
                    console.print(f"  {key}: {value}")
        else:
            console.print(f"[red]❌ Analysis failed: {result.get('error', 'Unknown error')}[/red]")


async def run_headless_mode(session: ClaySession, query: Optional[str], piped_input: Optional[str], output_format: str):
    """Run in headless mode - process query and exit."""
    import json

    # Combine query and piped input
    if piped_input and query:
        prompt = f"{piped_input}\n\n{query}"
    elif piped_input:
        prompt = piped_input
    elif query:
        prompt = query
    else:
        console.print("[red]Error: No input provided for headless mode[/red]")
        return

    response = await session.process_message(prompt)

    if output_format == "json":
        output = {"response": response, "status": "success"}
        console.print(json.dumps(output, indent=2))
    elif output_format == "stream-json":
        # Simulate streaming JSON output
        lines = response.split('\n')
        for i, line in enumerate(lines):
            output = {"line": i, "content": line, "final": i == len(lines) - 1}
            console.print(json.dumps(output))
    else:
        console.print(response)


async def run_continue_mode(session: ClaySession):
    """Continue the most recent conversation."""
    current_session = session.session_manager.get_current_session()
    if current_session:
        if session.load_session(current_session["id"]):
            console.print(f"[green]Continuing session {current_session['id']} ({len(current_session['messages'])} messages)[/green]")
            await run_interactive_mode(session, None)
        else:
            console.print("[red]Failed to load current session[/red]")
            await run_interactive_mode(session, None)
    else:
        console.print("[yellow]No previous session found - starting new session[/yellow]")
        await run_interactive_mode(session, None)


async def run_resume_mode(session: ClaySession, session_id: str):
    """Resume a specific session by ID."""
    if session.load_session(session_id):
        session_data = session.session_manager.get_session(session_id)
        console.print(f"[green]Resumed session {session_id} ({len(session_data['messages'])} messages)[/green]")
        await run_interactive_mode(session, None)
    else:
        console.print(f"[red]Session '{session_id}' not found[/red]")
        # List available sessions
        sessions = session.session_manager.list_sessions()
        if sessions:
            console.print("\n[cyan]Available sessions:[/cyan]")
            for s in sessions[:5]:  # Show first 5
                console.print(f"  {s['id']} - {s['last_updated'][:10]} ({s['message_count']} messages)")
        await run_interactive_mode(session, None)


async def run_interactive_mode(session: ClaySession, initial_query: Optional[str]):
    """Run in interactive mode."""
    history_file = Path.home() / ".clay_history"
    prompt_session = PromptSession(history=FileHistory(str(history_file)))

    # Handle initial query if provided
    if initial_query:
        response = await session.process_message(initial_query)
        console.print(Markdown(response))

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: prompt_session.prompt("clay> ")
            )

            if user_input.lower() in ["exit", "quit"]:
                console.print("[cyan]Goodbye![/cyan]")
                break
            elif user_input.lower() == "help":
                show_help()
                continue
            elif user_input.lower() == "clear":
                console.clear()
                continue

            response = await session.process_message(user_input)
            console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[cyan]Use 'exit' to quit[/cyan]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@click.group()
def main_cli():
    """Clay - Agentic Coding System"""
    pass


@main_cli.command()
def update():
    """Update Clay to the latest version."""
    console.print("[yellow]Update functionality not yet implemented[/yellow]")
    console.print("Please use: pip install --upgrade clay")


@main_cli.command()
def mcp():
    """Configure Model Context Protocol servers."""
    console.print("[yellow]MCP configuration not yet implemented[/yellow]")


def show_help():
    """Show help information."""
    help_text = """
# Clay Commands

- **exit/quit**: Exit the session
- **help**: Show this help message
- **clear**: Clear the screen

# CLI Options (like Claude Code):

- `clay` - Start interactive mode
- `clay "query"` - Start with initial query
- `clay -p "query"` - Headless mode (print and exit)
- `cat file | clay -p "query"` - Process piped content
- `clay -c` - Continue most recent conversation
- `clay -r session-id` - Resume specific session
- `clay --add-dir ../path` - Add working directories
- `clay --fast` - Use fast mode
- `clay --output-format json` - JSON output
- `clay --verbose` - Detailed logging

# Example Usage:

- `clay "Read the file main.py"`
- `clay -p "How many Python files are in this project?"`
- `clay --add-dir ../frontend --add-dir ../backend`
- `cat README.md | clay -p "Summarize this"`
    """
    console.print(Markdown(help_text))


# Add the main CLI to the group
main_cli.add_command(cli, name="main")


def main():
    """Main entry point."""
    # If no subcommand provided, run the main CLI
    import sys
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and not sys.argv[1] in ['update', 'mcp']):
        cli()
    else:
        main_cli()


if __name__ == "__main__":
    main()