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


console = Console()


class ClaySession:
    """Main session handler for Clay CLI."""

    def __init__(self, llm_provider=None, working_dir: str = ".", fast_mode: bool = False):
        self.llm_provider = llm_provider or get_default_provider()
        self.working_dir = Path(working_dir).resolve()
        self.fast_mode = fast_mode
        self.orchestrator = AgentOrchestrator()
        self.conversation = ConversationManager()
        self.setup_agents()

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

        self.orchestrator.register_agent(coding_agent)
        self.orchestrator.register_agent(research_agent)

    async def process_message(self, message: str) -> str:
        """Process a user message and return response."""
        self.conversation.add_user_message(message)

        context = AgentContext(
            working_directory=str(self.working_dir),
            conversation_history=self.conversation.get_history(),
            available_tools=[],
            metadata={}
        )

        agent_name = self.determine_agent(message)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Thinking with {agent_name}...", total=None)

            task_id = f"task_{len(self.orchestrator.tasks)}"
            agent_task = self.orchestrator.create_task(
                task_id=task_id,
                prompt=message,
                agent_name=agent_name
            )

            await self.orchestrator.submit_task(agent_task)
            result = await self.orchestrator.run_task(agent_task, context)

            progress.update(task, completed=True)

        if result.error:
            response = f"Error: {result.error}"
        else:
            response = result.output or "Task completed"

        self.conversation.add_assistant_message(response)
        return response

    def determine_agent(self, message: str) -> str:
        """Determine which agent to use based on message."""
        message_lower = message.lower()

        research_keywords = ["search", "find", "research", "look for", "grep", "analyze"]
        if any(keyword in message_lower for keyword in research_keywords):
            return "research_agent"

        return "coding_agent"


@click.group()
def cli():
    """Clay - Agentic Coding System"""
    pass


@cli.command()
@click.option("--provider", "-p", help="LLM provider (openai/anthropic/cloudrift)")
@click.option("--model", "-m", help="Model to use")
@click.option("--api-key", "-k", help="API key for provider")
@click.option("--fast", is_flag=True, help="Use fast mode for better performance")
def chat(provider: Optional[str], model: Optional[str], api_key: Optional[str], fast: bool):
    """Start an interactive chat session."""
    console.print(Panel.fit(
        "[bold cyan]Clay - Agentic Coding System[/bold cyan]\n"
        "Type 'help' for commands, 'exit' to quit",
        border_style="cyan"
    ))

    llm_provider = None
    if provider:
        try:
            llm_provider = create_llm_provider(provider, api_key, model)
            console.print(f"[green]Using {provider} provider[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: {e}[/yellow]")
            console.print("[yellow]Running without LLM provider (mock mode)[/yellow]")

    session = ClaySession(llm_provider, fast_mode=fast)
    history_file = Path.home() / ".clay_history"
    prompt_session = PromptSession(history=FileHistory(str(history_file)))

    async def run_session():
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

    asyncio.run(run_session())


@cli.command()
@click.argument("prompt")
@click.option("--provider", "-p", help="LLM provider (openai/anthropic/cloudrift)")
@click.option("--model", "-m", help="Model to use")
@click.option("--api-key", "-k", help="API key for provider")
@click.option("--fast", is_flag=True, help="Use fast mode for better performance")
def run(prompt: str, provider: Optional[str], model: Optional[str], api_key: Optional[str], fast: bool):
    """Run a single command."""
    llm_provider = None
    if provider:
        llm_provider = create_llm_provider(provider, api_key=api_key, model=model)

    session = ClaySession(llm_provider, fast_mode=fast)

    async def execute():
        response = await session.process_message(prompt)
        console.print(Markdown(response))

    asyncio.run(execute())


def show_help():
    """Show help information."""
    help_text = """
# Clay Commands

- **exit/quit**: Exit the session
- **help**: Show this help message
- **clear**: Clear the screen

# Example prompts:

- "Read the file main.py"
- "Search for TODO comments in the codebase"
- "Create a new Python script that..."
- "Run the tests"
- "Edit the config file to change..."
    """
    console.print(Markdown(help_text))


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()