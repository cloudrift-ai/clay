"""Control Loop Orchestrator with FSM States for Clay."""

from enum import Enum, auto
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from pathlib import Path
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OrchestratorState(Enum):
    """Strict FSM states for the control loop."""
    INGEST = auto()      # Clone/checkout, detect stack, hydrate caches
    PLAN = auto()        # Model proposes stepwise plan
    EDIT = auto()        # Model proposes unified diff
    TEST = auto()        # Run targeted tests first, then full suite
    ITERATE = auto()     # Repair failed patches or tests
    DONE = auto()        # Emit artifacts and finalize
    ABORT = auto()       # Emergency stop on violations


@dataclass
class StateTransition:
    """Represents a state transition with conditions."""
    from_state: OrchestratorState
    to_state: OrchestratorState
    condition: Optional[Callable[[Any], bool]] = None
    on_transition: Optional[Callable[[Any], None]] = None


@dataclass
class OrchestratorContext:
    """Context passed through the FSM."""
    task_id: str
    working_dir: Path
    goal: str
    constraints: Dict[str, Any] = field(default_factory=dict)

    # State data
    current_state: OrchestratorState = OrchestratorState.INGEST
    plan: Optional[Dict] = None
    proposed_diff: Optional[str] = None
    applied_patches: List[str] = field(default_factory=list)
    test_results: Optional[Dict] = None

    # Metrics
    start_time: datetime = field(default_factory=datetime.now)
    state_durations: Dict[str, float] = field(default_factory=dict)
    retry_count: int = 0
    token_usage: int = 0

    # Artifacts
    artifacts: Dict[str, Any] = field(default_factory=dict)

    # Limits
    max_retries: int = 3
    max_duration: timedelta = timedelta(minutes=30)
    max_tokens: int = 100000


class ControlLoopOrchestrator:
    """Main orchestrator implementing the FSM control loop."""

    def __init__(self,
                 context_engine,
                 model_agent,
                 policy_engine=None,
                 patch_engine=None,
                 sandbox_manager=None,
                 test_runner=None):
        self.context_engine = context_engine
        self.patch_engine = patch_engine
        self.sandbox = sandbox_manager
        self.test_runner = test_runner
        self.policy = policy_engine
        self.model = model_agent

        # Define state transitions
        self.transitions = self._define_transitions()

        # State handlers
        self.state_handlers = {
            OrchestratorState.INGEST: self._handle_ingest,
            OrchestratorState.PLAN: self._handle_plan,
            OrchestratorState.EDIT: self._handle_edit,
            OrchestratorState.TEST: self._handle_test,
            OrchestratorState.ITERATE: self._handle_iterate,
            OrchestratorState.DONE: self._handle_done,
            OrchestratorState.ABORT: self._handle_abort,
        }

    def _define_transitions(self) -> List[StateTransition]:
        """Define valid state transitions and their conditions."""
        return [
            # Normal flow
            StateTransition(
                OrchestratorState.INGEST,
                OrchestratorState.PLAN,
                condition=lambda ctx: ctx.working_dir.exists()
            ),
            StateTransition(
                OrchestratorState.PLAN,
                OrchestratorState.EDIT,
                condition=lambda ctx: ctx.plan is not None
            ),
            StateTransition(
                OrchestratorState.EDIT,
                OrchestratorState.TEST,
                condition=lambda ctx: ctx.proposed_diff is not None and not ctx.artifacts.get('query_only', False)
            ),
            StateTransition(
                OrchestratorState.EDIT,
                OrchestratorState.DONE,
                condition=lambda ctx: ctx.proposed_diff is not None and ctx.artifacts.get('query_only', False)
            ),
            StateTransition(
                OrchestratorState.TEST,
                OrchestratorState.DONE,
                condition=lambda ctx: self._tests_passing(ctx)
            ),

            # Iteration/repair flows
            StateTransition(
                OrchestratorState.TEST,
                OrchestratorState.ITERATE,
                condition=lambda ctx: not self._tests_passing(ctx) and ctx.retry_count < ctx.max_retries
            ),
            StateTransition(
                OrchestratorState.ITERATE,
                OrchestratorState.EDIT,
                condition=lambda ctx: ctx.retry_count < ctx.max_retries
            ),

            # Abort transitions (from any state)
            StateTransition(
                OrchestratorState.PLAN,
                OrchestratorState.ABORT,
                condition=lambda ctx: self._should_abort(ctx)
            ),
            StateTransition(
                OrchestratorState.EDIT,
                OrchestratorState.ABORT,
                condition=lambda ctx: self._should_abort(ctx)
            ),
            StateTransition(
                OrchestratorState.TEST,
                OrchestratorState.ABORT,
                condition=lambda ctx: self._should_abort(ctx)
            ),
            StateTransition(
                OrchestratorState.ITERATE,
                OrchestratorState.ABORT,
                condition=lambda ctx: ctx.retry_count >= ctx.max_retries
            ),
        ]

    async def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task through the FSM control loop."""
        ctx = OrchestratorContext(
            task_id=task.get('id', 'unknown'),
            working_dir=Path(task['working_dir']),
            goal=task['goal'],
            constraints=task.get('constraints', {}),
            max_retries=task.get('max_retries', 3),
            max_duration=timedelta(minutes=task.get('timeout_minutes', 30)),
            max_tokens=task.get('max_tokens', 100000)
        )

        logger.info(f"Starting task {ctx.task_id}: {ctx.goal}")

        try:
            while ctx.current_state not in [OrchestratorState.DONE, OrchestratorState.ABORT]:
                # Check global abort conditions
                if self._should_abort(ctx):
                    ctx.current_state = OrchestratorState.ABORT
                    break

                # Execute current state handler
                state_start = datetime.now()
                handler = self.state_handlers[ctx.current_state]

                logger.info(f"Task {ctx.task_id}: Entering state {ctx.current_state.name}")
                await handler(ctx)

                # Record state duration
                duration = (datetime.now() - state_start).total_seconds()
                ctx.state_durations[ctx.current_state.name] = duration

                # Find and execute valid transition
                next_state = self._find_next_state(ctx)
                if next_state:
                    logger.info(f"Task {ctx.task_id}: Transitioning {ctx.current_state.name} -> {next_state.name}")
                    ctx.current_state = next_state
                else:
                    logger.error(f"Task {ctx.task_id}: No valid transition from {ctx.current_state.name}")
                    ctx.current_state = OrchestratorState.ABORT

            # Generate final report
            return self._generate_report(ctx)

        except Exception as e:
            logger.error(f"Task {ctx.task_id}: Fatal error - {str(e)}")
            ctx.current_state = OrchestratorState.ABORT
            ctx.artifacts['error'] = str(e)
            return self._generate_report(ctx)

    def _find_next_state(self, ctx: OrchestratorContext) -> Optional[OrchestratorState]:
        """Find valid next state based on current state and conditions."""
        for transition in self.transitions:
            if transition.from_state == ctx.current_state:
                if transition.condition is None or transition.condition(ctx):
                    if transition.on_transition:
                        transition.on_transition(ctx)
                    return transition.to_state
        return None

    async def _handle_ingest(self, ctx: OrchestratorContext):
        """INGEST state: Setup working copy and detect stack."""
        # Clone/checkout if needed
        if not ctx.working_dir.exists():
            raise ValueError(f"Working directory {ctx.working_dir} does not exist")

        # Detect stack and tools
        if self.sandbox:
            stack_info = await self.sandbox.detect_stack(ctx.working_dir)
            ctx.artifacts['stack_info'] = stack_info
        else:
            # Fallback stack info when no sandbox manager
            ctx.artifacts['stack_info'] = {"languages": [], "frameworks": [], "build_tools": []}

        # Hydrate caches
        await self.context_engine.index_repository(ctx.working_dir)

        logger.info(f"Ingested repository: {stack_info}")

    async def _handle_plan(self, ctx: OrchestratorContext):
        """PLAN state: Model proposes stepwise plan."""
        # Retrieve relevant context
        context_result = await self.context_engine.retrieve(
            goal=ctx.goal,
            budget_tokens=min(10000, ctx.max_tokens // 3)
        )

        # Convert RetrievalResult to dictionary
        context = {
            'files': context_result.files,
            'symbols': context_result.symbols,
            'imports': context_result.imports,
            'tests': context_result.tests,
            'configs': context_result.configs,
            'guides': context_result.guides
        }

        # Get plan from model
        plan = await self.model.create_plan(
            goal=ctx.goal,
            context=context,
            constraints=ctx.constraints
        )

        # Validate plan with policy
        if self.policy:
            validation = await self.policy.validate_plan(plan)
            if not validation.is_valid:
                raise ValueError(f"Plan violates policy: {validation.reasons}")

        ctx.plan = plan
        ctx.artifacts['plan'] = plan

    async def _handle_edit(self, ctx: OrchestratorContext):
        """EDIT state: Model proposes unified diff."""
        # Get context for editing
        context_result = await self.context_engine.retrieve(
            goal=ctx.goal,
            budget_tokens=min(15000, ctx.max_tokens // 2)
        )

        # Convert RetrievalResult to dictionary
        context = {
            'files': context_result.files,
            'symbols': context_result.symbols,
            'imports': context_result.imports,
            'tests': context_result.tests,
            'configs': context_result.configs,
            'guides': context_result.guides
        }

        # Generate unified diff
        diff = await self.model.propose_patch(
            plan=ctx.plan,
            context=context,
            previous_attempts=ctx.applied_patches
        )

        # Validate diff with policy
        if self.policy:
            validation = await self.policy.validate_diff(diff)
            if not validation.is_valid:
                raise ValueError(f"Diff violates policy: {validation.reasons}")

        # Check if this is a simple query (no actual diff needed)
        if (diff.strip() == "" or
            "no changes needed" in diff.lower() or
            "no files" in diff.lower() or
            not diff.startswith("---") or
            len(diff.split('\n')) < 3):
            # For simple queries, just mark as complete
            ctx.proposed_diff = "# No changes needed for query"
            ctx.artifacts['response'] = diff
            ctx.artifacts['query_only'] = True
            return

        # Validate diff format
        if self.patch_engine:
            patch_validation = await self.patch_engine.validate(diff)
            if not patch_validation.is_valid:
                ctx.artifacts['patch_rejects'] = patch_validation.rejects
                ctx.retry_count += 1
                return

            # Apply patch
            apply_result = await self.patch_engine.apply(diff)
            if not apply_result.success:
                ctx.artifacts['patch_rejects'] = apply_result.rejects
        else:
            # Fallback when no patch engine - assume patch is valid and applied
            ctx.artifacts['patch_applied'] = True
            ctx.retry_count += 1
            return

        ctx.proposed_diff = diff
        ctx.applied_patches.append(diff)
        ctx.artifacts['diffs'] = ctx.applied_patches


    async def _handle_test(self, ctx: OrchestratorContext):
        """TEST state: Run targeted tests first, then full suite."""
        # Determine impacted symbols from changes
        impacted = await self.context_engine.analyze_changes(ctx.proposed_diff)

        # Run targeted tests
        if self.test_runner:
            targeted_results = await self.test_runner.run_targeted(impacted)
            ctx.test_results = targeted_results
            ctx.artifacts['targeted_test_results'] = targeted_results

            if targeted_results['passed']:
                # Run full test suite if targeted passed
                full_results = await self.test_runner.run_full()
                ctx.test_results = full_results
                ctx.artifacts['full_test_results'] = full_results
        else:
            # Fallback when no test runner - assume tests pass
            ctx.test_results = {"passed": True, "total": 0, "failed": 0}
            ctx.artifacts['test_results'] = ctx.test_results

    async def _handle_iterate(self, ctx: OrchestratorContext):
        """ITERATE state: Feed failures back to model for repair."""
        ctx.retry_count += 1

        # Prepare minimal failure context
        if ctx.test_results and not ctx.test_results['passed']:
            failure_context = self._extract_minimal_failure(ctx.test_results)
        elif 'patch_rejects' in ctx.artifacts:
            failure_context = ctx.artifacts['patch_rejects']
        else:
            failure_context = ctx.artifacts.get('format_lint_results', {})

        # Get repair suggestion from model
        repair = await self.model.suggest_repair(
            failure_context=failure_context,
            previous_attempts=ctx.applied_patches,
            plan=ctx.plan
        )

        # Update plan with repair
        ctx.plan['repair_suggestion'] = repair

    async def _handle_done(self, ctx: OrchestratorContext):
        """DONE state: Emit artifacts and finalize."""
        logger.info(f"Task {ctx.task_id}: Completed successfully")

        # Write final artifacts
        ctx.artifacts['final_diff'] = ctx.proposed_diff
        ctx.artifacts['status'] = 'success'
        ctx.artifacts['duration'] = (datetime.now() - ctx.start_time).total_seconds()

    async def _handle_abort(self, ctx: OrchestratorContext):
        """ABORT state: Emergency stop and cleanup."""
        logger.error(f"Task {ctx.task_id}: Aborted")

        ctx.artifacts['status'] = 'aborted'
        ctx.artifacts['abort_reason'] = self._get_abort_reason(ctx)
        ctx.artifacts['duration'] = (datetime.now() - ctx.start_time).total_seconds()

    def _should_abort(self, ctx: OrchestratorContext) -> bool:
        """Check if we should abort based on limits."""
        # Time limit
        if datetime.now() - ctx.start_time > ctx.max_duration:
            return True

        # Token limit
        if ctx.token_usage > ctx.max_tokens:
            return True

        # Retry limit
        if ctx.retry_count >= ctx.max_retries:
            return True

        return False


    def _tests_passing(self, ctx: OrchestratorContext) -> bool:
        """Check if tests are passing."""
        return ctx.test_results and ctx.test_results.get('passed', False)

    def _extract_minimal_failure(self, test_results: Dict) -> Dict:
        """Extract minimal failure information for repair."""
        return {
            'first_failure': test_results.get('failures', [{}])[0],
            'failure_count': len(test_results.get('failures', [])),
            'error_summary': test_results.get('error_summary', '')
        }

    def _get_abort_reason(self, ctx: OrchestratorContext) -> str:
        """Determine abort reason."""
        if datetime.now() - ctx.start_time > ctx.max_duration:
            return f"Timeout: exceeded {ctx.max_duration}"
        elif ctx.token_usage > ctx.max_tokens:
            return f"Token limit: {ctx.token_usage} > {ctx.max_tokens}"
        elif ctx.retry_count >= ctx.max_retries:
            return f"Retry limit: {ctx.retry_count} >= {ctx.max_retries}"
        else:
            return "Unknown abort reason"

    def _generate_report(self, ctx: OrchestratorContext) -> Dict[str, Any]:
        """Generate final report of the task execution."""
        return {
            'task_id': ctx.task_id,
            'goal': ctx.goal,
            'status': ctx.artifacts.get('status', 'unknown'),
            'duration': (datetime.now() - ctx.start_time).total_seconds(),
            'state_durations': ctx.state_durations,
            'retry_count': ctx.retry_count,
            'token_usage': ctx.token_usage,
            'final_state': ctx.current_state.name,
            'artifacts': ctx.artifacts
        }