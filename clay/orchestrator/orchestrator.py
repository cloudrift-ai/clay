"""Integrated orchestrator that combines all components."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .fsm import ControlLoopOrchestrator
from .context_engine import ContextEngine

logger = logging.getLogger(__name__)


class ClayOrchestrator:
    """Main orchestrator that integrates all components for intelligent code modification."""

    def __init__(self, agent, working_dir: Path, policy_config: Optional[Dict] = None):
        """Initialize the orchestrator with all components."""
        self.working_dir = working_dir
        self.agent = agent

        # Initialize all components
        self.context_engine = ContextEngine(working_dir)

        # Initialize the FSM orchestrator
        self.fsm_orchestrator = ControlLoopOrchestrator(
            context_engine=self.context_engine,
            model_agent=self.agent
        )

        logger.info(f"Initialized Clay orchestrator for {working_dir}")

    async def process_task(self, goal: str, constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a coding task using the FSM orchestrator."""

        # Validate working directory
        if not self.working_dir.exists():
            raise ValueError(f"Working directory {self.working_dir} does not exist")

        # Set up task
        task = {
            "id": f"clay_task_{hash(goal) % 10000}",
            "working_dir": str(self.working_dir),
            "goal": goal,
            "constraints": constraints or {},
            "max_retries": 3,
            "timeout_minutes": 30,
            "max_tokens": 100000
        }

        logger.info(f"Processing task: {goal}")

        try:
            # Run the task through the FSM
            result = await self.fsm_orchestrator.run_task(task)

            logger.info(f"Task completed with status: {result.get('status', 'unknown')}")
            return result

        except Exception as e:
            logger.error(f"Task failed with error: {e}")
            return {
                "task_id": task["id"],
                "goal": goal,
                "status": "error",
                "error": str(e),
                "duration": 0.0,
                "artifacts": {}
            }

    async def analyze_project(self) -> Dict[str, Any]:
        """Analyze the project structure without making changes."""

        logger.info("Analyzing project structure...")

        try:
            # Initialize context engine
            await self.context_engine.index_repository(self.working_dir)

            # Detect stack
            stack_info = await self.sandbox_manager.detect_stack(self.working_dir)

            # Get project stats
            stats = await self.context_engine.get_stats()

            return {
                "stack_info": stack_info,
                "stats": stats,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Project analysis failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def validate_changes(self, diff: str) -> Dict[str, Any]:
        """Validate proposed changes without applying them."""

        logger.info("Validating proposed changes...")

        try:
            # Validate with policy engine
            policy_result = await self.policy_engine.validate_diff(diff)

            # Validate patch format
            patch_result = await self.patch_engine.validate(diff)

            return {
                "policy_validation": {
                    "is_valid": policy_result.is_valid,
                    "violations": policy_result.violations,
                    "warnings": policy_result.warnings
                },
                "patch_validation": {
                    "is_valid": patch_result.is_valid,
                    "errors": patch_result.errors,
                    "warnings": patch_result.warnings,
                    "stats": patch_result.stats
                },
                "overall_valid": policy_result.is_valid and patch_result.is_valid
            }

        except Exception as e:
            logger.error(f"Change validation failed: {e}")
            return {
                "policy_validation": {"is_valid": False, "violations": [str(e)]},
                "patch_validation": {"is_valid": False, "errors": [str(e)]},
                "overall_valid": False
            }

    async def get_context_for_goal(self, goal: str, budget_tokens: int = 10000) -> Dict[str, Any]:
        """Get relevant context for a specific goal."""

        try:
            # Ensure context is indexed
            await self.context_engine.index_repository(self.working_dir)

            # Retrieve context
            result = await self.context_engine.retrieve(goal, budget_tokens)

            return {
                "symbols": result.symbols[:10],  # Top 10 symbols
                "files": result.files[:5],       # Top 5 files
                "imports": result.imports[:5],   # Top 5 imports
                "token_count": result.token_count,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


        logger.info("Updated policy configuration")

    async def cleanup(self):
        """Cleanup resources and temporary files."""
        try:
            # Rollback any pending changes
            await self.patch_engine.rollback()

            # Clear context engine cache if needed
            # (Context engine doesn't have explicit cleanup currently)

            logger.info("Orchestrator cleanup completed")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    def get_available_commands(self) -> Dict[str, Any]:
        """Get information about available commands in the project."""
        return asyncio.create_task(self.sandbox_manager.get_available_commands())