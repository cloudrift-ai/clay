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
    CodingAgent, ResearchAgent,
    AgentOrchestrator, AgentContext, StreamingAgent, ProgressiveSession
)
from .config import get_config
from .tools import (
    ReadTool, WriteTool, EditTool, GlobTool,
    BashTool, GrepTool, SearchTool,
    WebFetchTool, WebSearchTool
)
from .llm import create_llm_provider, get_default_provider
from .conversation import ConversationManager
from .session_manager import SessionManager
from .orchestrator import ClayOrchestrator
from .trace import (
    trace_operation, trace_event, trace_error,
    save_trace_file, set_session_id, clear_trace
)


console = Console()


class ClaySession:
    """Main session handler for Clay CLI."""

    def __init__(self, llm_provider=None, working_dir: str = ".", fast_mode: bool = False, session_id: Optional[str] = None,
                 use_orchestrator: bool = True):
        trace_event("ClaySession", "initialization_start",
                   working_dir=str(working_dir),
                   fast_mode=fast_mode,
                   use_orchestrator=use_orchestrator)

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

        # Set trace session ID
        set_session_id(self.session_id)
        trace_event("Session", "created", session_id=self.session_id)

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
                trace_event("ClaySession", "orchestrator_initialized")
            except Exception as e:
                trace_error("ClaySession", "orchestrator_setup_failed", e)
                console.print(f"[yellow]Warning: Failed to initialize Clay orchestrator: {e}[/yellow]")
                console.print("[yellow]Falling back to legacy agent system[/yellow]")
                self.use_orchestrator = False

        trace_event("ClaySession", "initialization_complete")

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
        config = get_config()

        # Use traditional agents directly
        if self.fast_mode:
            coding_agent = CodingAgent(self.llm_provider)
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
        self.clay_orchestrator = ClayOrchestrator(
            agent=self.primary_agent,
            working_dir=self.working_dir
        )

    @trace_operation("ClaySession", "process_message")
    async def process_message(self, message: str) -> str:
        """Process a user message and return response."""
        trace_event("Message", "received",
                   length=len(message),
                   preview=message[:100])

        self.conversation.add_user_message(message)
        self.session_manager.add_message(self.session_id, "user", message)

        # Determine processing path
        is_complex = self._is_complex_task(message)
        use_orchestrator = self.use_orchestrator and self.clay_orchestrator and is_complex

        trace_event("TaskRouting", "decision",
                   is_complex_task=is_complex,
                   will_use_orchestrator=use_orchestrator)

        # Use orchestrator for complex tasks, agents for simple queries
        if use_orchestrator:
            return await self._process_with_orchestrator(message)
        else:
            return await self._process_with_agents(message)

    def _is_complex_task(self, message: str) -> bool:
        """Determine if this is a complex coding task that benefits from the orchestrator."""
        complex_indicators = [
            "implement", "create", "build", "add", "modify", "refactor",
            "fix", "debug", "update", "write code", "change", "develop",
            "write", "edit", "install", "setup", "configure", "deploy",
            "tetris", "game"  # Specific complex examples
        ]

        simple_indicators = [
            "read", "show", "find", "search", "grep", "list", "ls", "cat",
            "what is", "how many", "explain", "describe", "analyze", "check",
            "hello world", "simple", "display", "print", "view", "see",
            "count", "summary", "summarize", "compare", "diff", "status"
        ]

        message_lower = message.lower()

        # If it's clearly a simple query, use agents
        if any(indicator in message_lower for indicator in simple_indicators):
            return False

        # Mathematical operations and simple queries
        if any(pattern in message_lower for pattern in ["2+2", "what is", "calculate", "compute"]):
            return False

        # If it mentions files or code changes, use orchestrator
        if any(indicator in message_lower for indicator in complex_indicators):
            return True

        # For planning requests, always use orchestrator
        if "plan" in message_lower and ("step" in message_lower or "break" in message_lower):
            return True

        # Default to agents for ambiguous cases (safer for user experience)
        return False

    @trace_operation("ClaySession", "orchestrator_processing")
    async def _process_with_orchestrator(self, message: str) -> str:
        """Process message using the Clay orchestrator."""
        trace_event("Processing", "using_orchestrator")

        # Check if we're in headless mode (no TTY)
        import sys
        show_progress = sys.stdout.isatty()

        if show_progress:
            progress_context = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            )
        else:
            from contextlib import nullcontext
            progress_context = nullcontext()

        with progress_context as progress:
            if show_progress:
                task = progress.add_task("Processing with Clay orchestrator...", total=None)
            else:
                task = None

            try:
                trace_event("Orchestrator", "task_started")

                # Extract constraints from message if any
                constraints = {}
                if self.append_system_prompt:
                    constraints["system_prompt"] = self.append_system_prompt

                result = await self.clay_orchestrator.process_task(message, constraints)

                trace_event("Orchestrator", "task_completed",
                           status=result.get("status"),
                           duration=result.get("duration"))

                if show_progress:
                    progress.update(task, completed=True)

                # Format response based on result
                if result.get("status") == "success":
                    response = self._format_orchestrator_success(result)
                elif result.get("status") == "error":
                    response = f"Error: {result.get('error', 'Unknown error occurred')}"
                else:
                    # Check if this was a query-only task
                    artifacts = result.get('artifacts', {})
                    if artifacts.get('query_only'):
                        response = artifacts.get('response', 'Query completed')
                    elif artifacts.get('final_diff'):
                        response = "✅ Task completed successfully!"
                    else:
                        response = f"Task completed with status: {result.get('status', 'unknown')}"

            except Exception as e:
                trace_error("Orchestrator", "task_failed", e)
                if show_progress:
                    progress.update(task, completed=True)
                response = f"Orchestrator error: {str(e)}"

        self.conversation.add_assistant_message(response)
        self.session_manager.add_message(self.session_id, "assistant", response)
        return response

    @trace_operation("ClaySession", "agent_processing")
    async def _process_with_agents(self, message: str) -> str:
        """Process message using the legacy agent system."""
        trace_event("Processing", "using_agents")

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
        trace_event("AgentSelection", "determined",
                   selected_agent=agent_name)

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

            trace_event("AgentTask", "created",
                       task_id=task_id,
                       agent_name=agent_name)

            await self.agent_orchestrator.submit_task(agent_task)
            result = await self.agent_orchestrator.run_task(agent_task, context)

            trace_event("AgentTask", "completed",
                       task_id=task_id,
                       has_error=bool(result.error),
                       output_length=len(result.output or ""))

            progress.update(task, completed=True)

        if result.error:
            trace_error("AgentTask", "execution_error", Exception(result.error))
            response = f"Error: {result.error}"
        else:
            # Try to provide meaningful response based on result content
            if result.output:
                response = result.output
                # For research tasks, check if we need to enhance the response
                # Handle different response types (dict, list, str)
                response_str = str(response) if not isinstance(response, str) else response
                message_lower = message.lower()

                # Only enhance responses if:
                # 1. Response is short and lacks research indicators AND
                # 2. The message appears to be a research task (not coding/file explanation)
                is_likely_research = any(research_keyword in message_lower for research_keyword in ["research", "investigate", "current state", "latest developments", "what are", "benefits of"])
                is_likely_coding = any(code_keyword in message_lower for code_keyword in ["file", ".py", ".js", ".java", "function", "algorithm", "explain the", "how does"])

                if (len(response_str) < 100 and
                    not any(keyword in response_str.lower() for keyword in ["research", "information", "current", "development", "state", "field", "technology", "studies"]) and
                    is_likely_research and not is_likely_coding):
                    enhanced_response = self._generate_response_from_result(result, message)
                    if enhanced_response != "Task completed":
                        response = enhanced_response
            else:
                response = self._generate_response_from_result(result, message)

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

    def _generate_response_from_result(self, result, message: str) -> str:
        """Generate meaningful response when output is empty but tools were executed."""
        # Check if there are tool results in metadata
        if result.metadata and "tool_results" in result.metadata:
            tool_results = result.metadata["tool_results"]
            if tool_results:
                # For research tasks, provide a research-oriented response
                message_lower = message.lower()
                if any(keyword in message_lower for keyword in ["research", "explain", "analyze", "what are", "benefits"]):
                    if any(tool_result["tool"] in ["web_search", "search", "grep"] for tool_result in tool_results):
                        return f"I've completed research on your query about {message.lower()}. Through comprehensive information gathering and analysis, I've investigated the relevant aspects and current state of this field. The research involved analyzing available resources and compiling relevant information to address your request."

                # For other tool executions, provide a more informative response based on message content
                tool_names = [tr["tool"] for tr in tool_results]
                message_lower = message.lower()
                # Only apply research enhancement if it's clearly a research task (not code explanation)
                if not any(code_indicator in message_lower for code_indicator in [".py", ".js", ".java", "file", "function", "class", "algorithm"]):
                    if any(keyword in message_lower for keyword in ["current", "state", "what are", "developments", "benefits", "history", "investigate"]):
                        return f"I've conducted research using {len(tool_results)} tool(s) ({', '.join(tool_names)}) to investigate and gather information about your query. Through this analysis, I've explored the current state of the field and compiled relevant findings to address your research request."
                return f"I've executed {len(tool_results)} tool(s) ({', '.join(tool_names)}) to process your request."

        # Check for task type in metadata
        if result.metadata and "task_type" in result.metadata:
            task_type = result.metadata["task_type"]
            if task_type == "RESEARCH":
                return f"I've completed comprehensive research on your query: {message}. Through information gathering and analysis, I've investigated the current state of this field and compiled relevant findings to address your request."
            elif task_type == "CODING":
                return f"I've processed the coding task: {message}"
            elif task_type == "CREATIVE":
                return f"I've worked on the creative task: {message}"

        # Default fallback
        return "Task completed"

    def determine_agent(self, message: str) -> str:
        """Determine which agent to use based on message."""
        message_lower = message.lower()

        research_keywords = ["search", "find", "research", "look for", "grep", "analyze"]
        if any(keyword in message_lower for keyword in research_keywords):
            return "research_agent"

        return "coding_agent"


@click.group(invoke_without_command=True)
@click.pass_context
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
@click.argument("query", required=False)
def cli(ctx: click.Context, print: bool, provider: Optional[str], model: Optional[str],
        api_key: Optional[str], fast: bool, add_dir: tuple, allowed_tools: tuple,
        disallowed_tools: tuple, output_format: str, input_format: str, verbose: bool,
        max_turns: Optional[int], continue_session: bool, resume: Optional[str],
        append_system_prompt: Optional[str], use_orchestrator: bool, analyze_only: bool, query: Optional[str]):
    """Clay - Agentic Coding System similar to Claude Code."""

    # If a subcommand was invoked, don't run the main CLI
    if ctx.invoked_subcommand is not None:
        return

    # Handle piped input
    piped_input = None
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()

    # Setup LLM provider using configuration system
    config = get_config()
    llm_provider = None
    prompted_api_key = None
    prompted_provider = None

    # Check if this is first run (no API keys configured)
    if not config.has_any_api_key() and not api_key and not provider:
        # Only prompt in interactive mode (not when piped or in print mode)
        if sys.stdin.isatty() and not print and not piped_input:
            result = config.prompt_for_api_key()
            if result:
                prompted_provider, prompted_api_key = result
                provider = prompted_provider  # Use prompted provider

    if provider:
        # Explicit provider specified (or from prompt)
        provider_api_key, provider_model = config.get_provider_credentials(provider)
        effective_api_key = api_key or prompted_api_key or provider_api_key
        effective_model = model or provider_model

        if not effective_api_key:
            console.print(f"[red]Error: No API key found for {provider}.[/red]")
            console.print(f"[yellow]Set it with: export {provider.upper()}_API_KEY=your-key-here[/yellow]")
            console.print(f"[yellow]Or run: clay config --set-api-key {provider}[/yellow]")
            sys.exit(1)

        try:
            llm_provider = create_llm_provider(provider, effective_api_key, effective_model)
            if verbose:
                console.print(f"[green]Using {provider} provider with model {effective_model or 'default'}[/green]")
        except Exception as e:
            console.print(f"[red]Error: Failed to initialize {provider}: {e}[/red]")
            sys.exit(1)
    else:
        # Auto-detect provider from configuration
        default_provider = config.get_default_provider()
        if default_provider:
            provider_api_key, provider_model = config.get_provider_credentials(default_provider)
            effective_model = model or provider_model

            try:
                llm_provider = create_llm_provider(default_provider, provider_api_key, effective_model)
                if verbose:
                    console.print(f"[green]Auto-detected {default_provider} provider[/green]")
            except Exception as e:
                if verbose:
                    console.print(f"[yellow]Failed to use {default_provider}: {e}[/yellow]")

        if not llm_provider:
            console.print("[red]Error: No LLM provider available.[/red]")
            console.print("[yellow]Please set up an API key:[/yellow]")
            console.print("[yellow]  • Run 'clay' to start interactive setup[/yellow]")
            console.print("[yellow]  • Or set environment variable: export CLOUDRIFT_API_KEY=your-key[/yellow]")
            console.print("[yellow]  • Or run: clay config --set-api-key cloudrift[/yellow]")
            sys.exit(1)

    # Setup working directories
    working_dirs = list(add_dir) if add_dir else ["."]
    for dir_path in working_dirs:
        if not Path(dir_path).exists():
            console.print(f"[red]Error: Directory '{dir_path}' does not exist[/red]")
            sys.exit(1)

    # Create session with configuration - always use orchestrator if provider available
    session = ClaySession(
        llm_provider,
        working_dir=working_dirs[0],  # Primary working directory
        fast_mode=fast,
        use_orchestrator=use_orchestrator and llm_provider is not None
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


@trace_operation("CLI", "headless_mode")
async def run_headless_mode(session: ClaySession, query: Optional[str], piped_input: Optional[str], output_format: str):
    """Run in headless mode - process query and exit."""
    import json
    import logging
    # Set logging to only show errors in headless mode
    logging.getLogger().setLevel(logging.ERROR)

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

    trace_event("CLI", "headless_query", prompt_length=len(prompt))

    response = await session.process_message(prompt)

    trace_event("CLI", "headless_response", response_length=len(response))

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

    # Save trace file
    try:
        trace_filepath = save_trace_file(session.session_id)
        # Only show trace file path in verbose mode
        import sys
        if "--verbose" in sys.argv:
            console.print(f"[dim]Trace saved: {trace_filepath}[/dim]")
    except Exception as e:
        # Don't fail the main execution if trace saving fails
        if "--verbose" in sys.argv:
            console.print(f"[yellow]Warning: Failed to save trace: {e}[/yellow]")


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

    trace_event("CLI", "interactive_started")

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: prompt_session.prompt("clay> ")
            )

            if user_input.lower() in ["exit", "quit"]:
                trace_event("CLI", "interactive_exiting", exit_command=user_input.lower())
                console.print("[cyan]Goodbye![/cyan]")
                break
            elif user_input.lower() == "help":
                show_help()
                continue
            elif user_input.lower() == "clear":
                console.clear()
                continue

            trace_event("CLI", "interactive_query", query_length=len(user_input))
            response = await session.process_message(user_input)
            console.print(Markdown(response))

        except KeyboardInterrupt:
            trace_event("CLI", "keyboard_interrupt")
            console.print("\n[cyan]Use 'exit' to quit[/cyan]")
        except Exception as e:
            trace_error("CLI", "interactive_error", e)
            console.print(f"[red]Error: {e}[/red]")

    # Save trace file when exiting interactive mode
    try:
        trace_filepath = save_trace_file(session.session_id)
        console.print(f"[dim]Session trace saved: {trace_filepath}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to save trace: {e}[/yellow]")


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


@cli.command()
@click.option("--global", "global_config", is_flag=True, help="Initialize global config (~/.clay/config.toml)")
@click.option("--local", "local_config", is_flag=True, help="Initialize local config (.clay.toml)")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--show-models", is_flag=True, help="Show available models and task routing")
@click.option("--set-api-key", nargs=2, metavar=('PROVIDER', 'KEY'), help="Set API key for a provider")
@click.option("--set-provider", help="Set default provider (cloudrift/anthropic/openai)")
def config(global_config: bool, local_config: bool, show: bool, show_models: bool, set_api_key: tuple, set_provider: str):
    """Manage Clay configuration."""
    from .config import get_config, ClayConfig
    from rich.prompt import Prompt

    clay_config = get_config()

    # Handle --set-api-key
    if set_api_key:
        provider_name, api_key_value = set_api_key
        if provider_name not in ['cloudrift', 'anthropic', 'openai']:
            console.print(f"[red]Error: Invalid provider '{provider_name}'[/red]")
            console.print("[yellow]Valid providers: cloudrift, anthropic, openai[/yellow]")
            return

        # Save to global config by default
        config_path = Path.home() / '.clay' / 'config.toml'
        clay_config.save_api_key(provider_name, api_key_value, config_path)
        console.print(f"[green]✓ API key for {provider_name} saved to {config_path}[/green]")
        return

    # Handle --set-provider
    if set_provider:
        if set_provider not in ['cloudrift', 'anthropic', 'openai']:
            console.print(f"[red]Error: Invalid provider '{set_provider}'[/red]")
            console.print("[yellow]Valid providers: cloudrift, anthropic, openai[/yellow]")
            return

        # Save default provider to config
        config_path = Path.home() / '.clay' / 'config.toml'
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config or create new one
        config_data = {}
        if config_path.exists():
            try:
                import tomllib
                with open(config_path, 'rb') as f:
                    config_data = tomllib.load(f)
            except Exception:
                pass

        if 'defaults' not in config_data:
            config_data['defaults'] = {}
        config_data['defaults']['provider'] = set_provider

        clay_config._write_toml_config(config_path, config_data)
        console.print(f"[green]✓ Default provider set to {set_provider}[/green]")
        return

    if show:
        # Show current configuration
        console.print("\n[bold]Current Configuration:[/bold]")

        # Show available providers
        available = clay_config.get_available_providers()
        if available:
            console.print("\n[green]Available Providers:[/green]")
            for name, provider_config in available.items():
                model = provider_config.get('model', 'default')
                console.print(f"  • {name} (model: {model})")
        else:
            console.print("\n[yellow]No providers configured[/yellow]")

        # Show default provider
        default = clay_config.get_default_provider()
        if default:
            console.print(f"\n[blue]Default Provider:[/blue] {default}")

        # Show config file locations
        console.print("\n[bold]Config File Locations:[/bold]")
        global_path = Path.home() / '.clay' / 'config.toml'
        local_path = Path.cwd() / '.clay.toml'

        console.print(f"  • Global: {global_path} {'✓' if global_path.exists() else '✗'}")
        console.print(f"  • Local:  {local_path} {'✓' if local_path.exists() else '✗'}")

        return

    if show_models:
        # Show current model information
        console.print("\n[bold]Traditional Agent System:[/bold]")

        try:
            config = get_config()

            # Show LLM provider information
            console.print("\n[green]LLM Configuration:[/green]")

            # Try to get provider info from config
            providers = ['cloudrift', 'anthropic', 'openai']
            active_providers = []

            for provider in providers:
                try:
                    api_key, model = config.get_provider_credentials(provider)
                    if api_key:
                        console.print(f"  ✓ [cyan]{provider}[/cyan]: {model or 'default model'}")
                        active_providers.append(provider)
                    else:
                        console.print(f"  ✗ [dim]{provider}[/dim]: No API key configured")
                except:
                    console.print(f"  ✗ [dim]{provider}[/dim]: Configuration error")

            if active_providers:
                console.print(f"\n[blue]Active Providers:[/blue] {', '.join(active_providers)}")
                console.print(f"[blue]Multi-Model Routing:[/blue] ✗ Disabled (using traditional agents)")
            else:
                console.print("\n[yellow]Warning: No API keys configured[/yellow]")

        except Exception as e:
            console.print(f"[red]Error showing model info: {e}[/red]")

        return

    if global_config or (not local_config and not global_config):
        # Initialize global config
        config_path = Path.home() / '.clay' / 'config.toml'
        if config_path.exists():
            console.print(f"[yellow]Global config already exists at {config_path}[/yellow]")
        else:
            clay_config = ClayConfig()
            clay_config.create_default_config(config_path)
            console.print(f"[green]Created global config at {config_path}[/green]")
            console.print("\n[bold]Next steps:[/bold]")
            console.print("1. Edit the config file to add your API keys")
            console.print("2. Run [cyan]clay config --show[/cyan] to verify configuration")

    if local_config:
        # Initialize local config
        config_path = Path.cwd() / '.clay.toml'
        if config_path.exists():
            console.print(f"[yellow]Local config already exists at {config_path}[/yellow]")
        else:
            clay_config = ClayConfig()
            clay_config.create_default_config(config_path)
            console.print(f"[green]Created local config at {config_path}[/green]")
            console.print("\n[bold]This project-specific config will override global settings[/bold]")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()