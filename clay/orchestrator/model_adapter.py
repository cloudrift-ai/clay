"""Model Agent Adapter for integrating Clay's LLM agents with the orchestrator."""

from typing import Dict, Any, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelAdapter:
    """Adapter to connect Clay's LLM agents with the orchestrator."""

    def __init__(self, agent):
        self.agent = agent

    async def create_plan(self, goal: str, context: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Create a stepwise plan using the model."""

        # Build context string from retrieval results
        context_str = self._build_context_string(context)

        # Create planning prompt
        planning_prompt = f"""
Create a detailed step-by-step plan to achieve this goal: {goal}

CONTEXT:
{context_str}

CONSTRAINTS:
{json.dumps(constraints, indent=2)}

REQUIREMENTS:
- Make incremental changes only, no full file rewrites
- Inspect the project structure first
- Use unified diffs for changes
- Consider test impact and coverage
- Follow existing code patterns and conventions

Provide a JSON response with this structure:
{{
    "steps": [
        {{
            "id": 1,
            "description": "Brief step description",
            "action": "analyze|edit|test",
            "files": ["file1.py", "file2.py"],
            "rationale": "Why this step is needed"
        }}
    ],
    "estimated_changes": 50,
    "risk_level": "low|medium|high",
    "dependencies": {{"add": [], "remove": []}},
    "test_strategy": "Description of testing approach"
}}
"""

        # Get response from agent (using dummy context)
        from ..agents import AgentContext
        dummy_context = AgentContext(
            working_directory=".",
            conversation_history=[],
            available_tools=[],
            metadata={}
        )
        result = await self.agent.think(planning_prompt, dummy_context)
        response = result.output or ""

        try:
            # Parse JSON response
            plan = self._extract_json_from_response(response)

            # Validate plan structure
            if not self._is_valid_plan(plan):
                raise ValueError("Invalid plan structure returned by model")

            return plan

        except Exception as e:
            logger.error(f"Failed to parse plan from model: {e}")
            # Return fallback plan
            return {
                "steps": [
                    {
                        "id": 1,
                        "description": "Analyze project structure",
                        "action": "analyze",
                        "files": [],
                        "rationale": "Understanding codebase before changes"
                    }
                ],
                "estimated_changes": 10,
                "risk_level": "low",
                "dependencies": {"add": [], "remove": []},
                "test_strategy": "Run existing tests"
            }

    async def propose_patch(self, plan: Dict[str, Any], context: Dict[str, Any],
                          previous_attempts: List[str]) -> str:
        """Propose a unified diff patch based on the plan."""

        context_str = self._build_context_string(context)

        # Build previous attempts context
        attempts_str = ""
        if previous_attempts:
            attempts_str = f"\nPREVIOUS ATTEMPTS:\n{len(previous_attempts)} previous patches were applied"

        patch_prompt = f"""
Based on this plan, create a unified diff patch:

PLAN:
{json.dumps(plan, indent=2)}

CONTEXT:
{context_str}
{attempts_str}

REQUIREMENTS:
- Generate ONLY a unified diff format patch
- Make minimal, targeted changes
- Preserve existing code style and patterns
- Include proper context lines for reliable application
- Focus on the next logical step from the plan

Output ONLY the unified diff, starting with --- and +++.
Do not include any other text or explanations.
"""

        # Get response from agent (using dummy context)
        from ..agents import AgentContext
        dummy_context = AgentContext(
            working_directory=".",
            conversation_history=[],
            available_tools=[],
            metadata={}
        )
        result = await self.agent.think(patch_prompt, dummy_context)
        response = result.output or ""

        # Extract diff from response (might be wrapped in code blocks)
        diff = self._extract_diff_from_response(response)

        return diff

    async def suggest_repair(self, failure_context: Dict[str, Any],
                           previous_attempts: List[str], plan: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest repair based on failure context."""

        repair_prompt = f"""
The previous change failed. Analyze the failure and suggest a repair:

FAILURE CONTEXT:
{json.dumps(failure_context, indent=2)}

ORIGINAL PLAN:
{json.dumps(plan, indent=2)}

PREVIOUS ATTEMPTS:
{len(previous_attempts)} patches have been tried

Provide a JSON response with repair suggestions:
{{
    "analysis": "Brief analysis of why it failed",
    "repair_strategy": "What approach to take",
    "modified_plan": {{
        "steps": [...],
        "changes": "Description of plan modifications"
    }},
    "confidence": "low|medium|high"
}}
"""

        # Get response from agent (using dummy context)
        from ..agents import AgentContext
        dummy_context = AgentContext(
            working_directory=".",
            conversation_history=[],
            available_tools=[],
            metadata={}
        )
        result = await self.agent.think(repair_prompt, dummy_context)
        response = result.output or ""

        try:
            repair = self._extract_json_from_response(response)
            return repair
        except Exception as e:
            logger.error(f"Failed to parse repair suggestion: {e}")
            return {
                "analysis": "Unable to analyze failure",
                "repair_strategy": "Simplify approach and retry",
                "modified_plan": plan,
                "confidence": "low"
            }

    def _build_context_string(self, context: Dict[str, Any]) -> str:
        """Build context string from retrieval results."""
        parts = []

        if 'symbols' in context:
            symbols = context['symbols'][:10]  # Limit to top 10
            if symbols:
                parts.append("RELEVANT SYMBOLS:")
                for symbol in symbols:
                    parts.append(f"- {symbol.get('name', 'unknown')} ({symbol.get('type', 'unknown')})")

        if 'files' in context:
            files = context['files'][:5]  # Limit to top 5
            if files:
                parts.append("\nRELEVANT FILES:")
                for file_info in files:
                    parts.append(f"- {file_info.get('path', 'unknown')}")
                    if 'content' in file_info:
                        # Include first few lines
                        lines = file_info['content'].split('\n')[:10]
                        parts.append("  " + "\n  ".join(lines))
                        if len(file_info['content'].split('\n')) > 10:
                            parts.append("  ...")

        if 'imports' in context:
            imports = context['imports'][:5]
            if imports:
                parts.append("\nRELEVANT IMPORTS:")
                for imp in imports:
                    parts.append(f"- {imp}")

        return "\n".join(parts) if parts else "No specific context available"

    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from model response, handling markdown blocks."""
        # Try to extract JSON from markdown code blocks first
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end != -1:
                json_content = response[start:end].strip()
                return json.loads(json_content)

        # Try to find JSON object in response
        if "{" in response and "}" in response:
            start = response.find("{")
            # Find matching closing brace
            brace_count = 0
            end = start
            for i, char in enumerate(response[start:], start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            if end > start:
                json_content = response[start:end]
                return json.loads(json_content)

        raise ValueError("No valid JSON found in response")

    def _extract_diff_from_response(self, response: str) -> str:
        """Extract unified diff from model response."""
        # Check if wrapped in code blocks
        if "```diff" in response:
            start = response.find("```diff") + 7
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()

        if "```" in response and ("---" in response or "+++" in response):
            start = response.find("```") + 3
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()

        # Look for diff markers
        lines = response.split('\n')
        diff_lines = []
        in_diff = False

        for line in lines:
            if line.startswith('---') or line.startswith('+++'):
                in_diff = True

            if in_diff:
                diff_lines.append(line)

            # Stop if we hit a non-diff line after starting
            if in_diff and line and not any(line.startswith(prefix) for prefix in
                                           ['---', '+++', '@@', '+', '-', ' ', '\\']):
                break

        if diff_lines:
            return '\n'.join(diff_lines)

        # Return the response as-is if no special formatting detected
        return response.strip()

    def _is_valid_plan(self, plan: Dict[str, Any]) -> bool:
        """Validate plan structure."""
        required_keys = ['steps', 'estimated_changes', 'risk_level']

        if not all(key in plan for key in required_keys):
            return False

        if not isinstance(plan['steps'], list) or not plan['steps']:
            return False

        # Validate step structure
        for step in plan['steps']:
            if not isinstance(step, dict):
                return False
            if 'description' not in step or 'action' not in step:
                return False

        return True