"""CLI interface for Clay."""

import asyncio
import sys
from pathlib import Path

from clay.orchestrator.orchestrator import ClayOrchestrator


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: clay <task>")
        sys.exit(1)

    task = " ".join(sys.argv[1:])

    # Create traces directory for CLI
    traces_dir = Path("_trace")
    traces_dir.mkdir(exist_ok=True)

    print(f"🚀 Clay CLI - Processing task: {task}")

    try:
        # Execute the task with automatic trace saving
        orchestrator = ClayOrchestrator(traces_dir=traces_dir)
        plan = await orchestrator.process_task(task)

        # Display results
        print(f"✅ Task completed!")
        print(f"📝 Completed steps: {len(plan.completed)}")
        print(f"📋 Remaining todos: {len(plan.todo)}")
        print(f"📊 Debug files saved to: {traces_dir}/")

        # Show final message if available
        if plan.completed:
            last_step = plan.completed[-1]
            if last_step.tool_name == "message" and last_step.result:
                output = last_step.result.get("output", "")
                if output:
                    print(f"\n💬 Result: {output}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())