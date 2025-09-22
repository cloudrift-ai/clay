"""Patch Engine for reliable unified diff application."""

import difflib
import hashlib
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Hunk:
    """Represents a single hunk in a diff."""
    original_start: int
    original_count: int
    modified_start: int
    modified_count: int
    context_before: List[str] = field(default_factory=list)
    removals: List[str] = field(default_factory=list)
    additions: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)


@dataclass
class FilePatch:
    """Represents patches for a single file."""
    original_file: str
    modified_file: str
    original_hash: Optional[str] = None
    hunks: List[Hunk] = field(default_factory=list)


@dataclass
class PatchValidation:
    """Results of patch validation."""
    is_valid: bool
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rejects: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ApplyResult:
    """Results of patch application."""
    success: bool
    applied_hunks: int = 0
    failed_hunks: int = 0
    rejects: List[Dict[str, Any]] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)


@dataclass
class RejectInfo:
    """Information about a rejected hunk."""
    file: str
    hunk_index: int
    original_lines: List[str]
    expected_context: List[str]
    actual_context: List[str]
    reason: str


class PatchEngine:
    """Engine for validating and applying unified diffs."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.original_contents: Dict[Path, str] = {}
        self.formatter_diff: Optional[str] = None

    async def validate(self, diff: str) -> PatchValidation:
        """Validate a unified diff."""
        validation = PatchValidation(is_valid=True)

        try:
            patches = self._parse_unified_diff(diff)

            if not patches:
                validation.is_valid = False
                validation.errors.append("No valid patches found in diff")
                return validation

            validation.stats['total_files'] = len(patches)
            validation.stats['total_hunks'] = sum(len(p.hunks) for p in patches)
            validation.stats['total_additions'] = 0
            validation.stats['total_deletions'] = 0

            for patch in patches:
                # Check file exists
                file_path = self.working_dir / patch.original_file

                if not file_path.exists() and patch.original_file != '/dev/null':
                    validation.warnings.append(f"File {patch.original_file} does not exist")

                # Validate file hash if provided
                if patch.original_hash and file_path.exists():
                    current_hash = self._compute_file_hash(file_path)
                    if current_hash != patch.original_hash:
                        validation.is_valid = False
                        validation.errors.append(
                            f"File {patch.original_file} hash mismatch: "
                            f"expected {patch.original_hash}, got {current_hash}"
                        )

                # Count changes
                for hunk in patch.hunks:
                    validation.stats['total_additions'] += len(hunk.additions)
                    validation.stats['total_deletions'] += len(hunk.removals)

                    # Check for whole file rewrites (too many changes)
                    if file_path.exists():
                        file_lines = file_path.read_text().count('\n')
                        change_ratio = (len(hunk.additions) + len(hunk.removals)) / max(file_lines, 1)
                        if change_ratio > 0.8:
                            validation.warnings.append(
                                f"Hunk in {patch.original_file} changes {change_ratio:.0%} of file"
                            )

            # Check for policy violations
            if validation.stats['total_additions'] > 1000:
                validation.warnings.append(f"Large patch: {validation.stats['total_additions']} additions")

            if validation.stats['total_deletions'] > 500:
                validation.warnings.append(f"Large deletion: {validation.stats['total_deletions']} deletions")

        except Exception as e:
            validation.is_valid = False
            validation.errors.append(f"Failed to parse diff: {str(e)}")

        return validation

    async def apply(self, diff: str) -> ApplyResult:
        """Apply a unified diff to the working directory."""
        result = ApplyResult(success=True)

        try:
            patches = self._parse_unified_diff(diff)

            for patch in patches:
                file_path = self.working_dir / patch.original_file

                # Handle file creation
                if patch.original_file == '/dev/null':
                    new_file_path = self.working_dir / patch.modified_file
                    new_content = '\n'.join(
                        line for hunk in patch.hunks
                        for line in hunk.additions
                    )
                    new_file_path.parent.mkdir(parents=True, exist_ok=True)
                    new_file_path.write_text(new_content)
                    result.modified_files.append(str(new_file_path))
                    result.applied_hunks += len(patch.hunks)
                    continue

                # Handle file deletion
                if patch.modified_file == '/dev/null':
                    if file_path.exists():
                        file_path.unlink()
                        result.modified_files.append(str(file_path))
                        result.applied_hunks += len(patch.hunks)
                    continue

                # Apply hunks to existing file
                if not file_path.exists():
                    result.success = False
                    result.rejects.append({
                        'file': patch.original_file,
                        'reason': 'File not found'
                    })
                    continue

                # Store original content for rollback
                original_content = file_path.read_text()
                self.original_contents[file_path] = original_content

                # Apply hunks
                modified_content = await self._apply_hunks_to_file(
                    original_content,
                    patch.hunks,
                    patch.original_file,
                    result
                )

                if modified_content is not None:
                    file_path.write_text(modified_content)
                    result.modified_files.append(str(file_path))
                else:
                    result.success = False

        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            result.success = False
            result.rejects.append({
                'reason': f'Patch application failed: {str(e)}'
            })

        return result

    async def _apply_hunks_to_file(
        self,
        content: str,
        hunks: List[Hunk],
        filename: str,
        result: ApplyResult
    ) -> Optional[str]:
        """Apply hunks to file content using fuzzy matching."""
        lines = content.split('\n')

        # Sort hunks by line number (reverse to apply from bottom up)
        sorted_hunks = sorted(hunks, key=lambda h: h.original_start, reverse=True)

        for hunk_idx, hunk in enumerate(sorted_hunks):
            # Try exact match first
            success = self._apply_hunk_exact(lines, hunk)

            if not success:
                # Try fuzzy match
                success, match_line = self._apply_hunk_fuzzy(lines, hunk)

                if not success:
                    # Reject hunk
                    result.failed_hunks += 1
                    result.rejects.append({
                        'file': filename,
                        'hunk': hunk_idx,
                        'expected_context': hunk.context_before + hunk.removals + hunk.context_after,
                        'reason': 'Could not find matching context'
                    })
                else:
                    result.applied_hunks += 1
                    logger.info(f"Applied hunk {hunk_idx} with fuzzy match at line {match_line}")
            else:
                result.applied_hunks += 1

        return '\n'.join(lines) if result.failed_hunks == 0 else None

    def _apply_hunk_exact(self, lines: List[str], hunk: Hunk) -> bool:
        """Apply a hunk using exact line matching."""
        start_line = hunk.original_start - 1  # Convert to 0-based

        # Build expected content
        expected = hunk.context_before + hunk.removals + hunk.context_after

        # Check if exact match exists
        if start_line + len(expected) > len(lines):
            return False

        actual = lines[start_line:start_line + len(expected)]

        # Strip whitespace for comparison
        expected_stripped = [line.rstrip() for line in expected]
        actual_stripped = [line.rstrip() for line in actual]

        if expected_stripped != actual_stripped:
            return False

        # Apply the change
        replacement = hunk.context_before + hunk.additions + hunk.context_after
        lines[start_line:start_line + len(expected)] = replacement

        return True

    def _apply_hunk_fuzzy(self, lines: List[str], hunk: Hunk) -> Tuple[bool, int]:
        """Apply a hunk using fuzzy matching."""
        # Build search pattern from context and removals
        search_pattern = hunk.context_before + hunk.removals + hunk.context_after

        if not search_pattern:
            return False, -1

        # Search for pattern in file
        best_match = None
        best_score = 0.0
        search_window = 20  # Lines to search around expected position

        start = max(0, hunk.original_start - search_window)
        end = min(len(lines), hunk.original_start + search_window)

        for i in range(start, end - len(search_pattern) + 1):
            window = lines[i:i + len(search_pattern)]
            score = self._similarity_score(search_pattern, window)

            if score > best_score and score > 0.8:  # 80% similarity threshold
                best_score = score
                best_match = i

        if best_match is not None:
            # Apply the change at best match
            replacement = hunk.context_before + hunk.additions + hunk.context_after
            lines[best_match:best_match + len(search_pattern)] = replacement
            return True, best_match

        return False, -1

    def _similarity_score(self, pattern: List[str], window: List[str]) -> float:
        """Calculate similarity between two line sequences."""
        if len(pattern) != len(window):
            return 0.0

        matches = sum(
            1 for p, w in zip(pattern, window)
            if p.strip() == w.strip()
        )

        return matches / len(pattern)

    def _parse_unified_diff(self, diff: str) -> List[FilePatch]:
        """Parse a unified diff into structured patches."""
        patches = []
        current_patch = None
        current_hunk = None
        in_hunk = False

        for line in diff.split('\n'):
            # File header
            if line.startswith('--- '):
                if current_patch and current_hunk:
                    current_patch.hunks.append(current_hunk)
                    current_hunk = None

                if current_patch:
                    patches.append(current_patch)

                parts = line[4:].split('\t')
                current_patch = FilePatch(
                    original_file=parts[0],
                    modified_file=''
                )

            elif line.startswith('+++ '):
                if current_patch:
                    parts = line[4:].split('\t')
                    current_patch.modified_file = parts[0]

            # Hunk header
            elif line.startswith('@@'):
                if current_hunk:
                    current_patch.hunks.append(current_hunk)

                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if match:
                    current_hunk = Hunk(
                        original_start=int(match.group(1)),
                        original_count=int(match.group(2) or '1'),
                        modified_start=int(match.group(3)),
                        modified_count=int(match.group(4) or '1')
                    )
                    in_hunk = True

            # Hunk content
            elif in_hunk and current_hunk:
                if line.startswith('-'):
                    current_hunk.removals.append(line[1:])
                elif line.startswith('+'):
                    current_hunk.additions.append(line[1:])
                elif line.startswith(' '):
                    # Context line
                    if current_hunk.removals or current_hunk.additions:
                        current_hunk.context_after.append(line[1:])
                    else:
                        current_hunk.context_before.append(line[1:])
                elif line.startswith('\\'):
                    # "No newline at end of file" - ignore
                    pass
                else:
                    # End of hunk
                    in_hunk = False

        # Add final hunk and patch
        if current_hunk:
            current_patch.hunks.append(current_hunk)
        if current_patch:
            patches.append(current_patch)

        return patches

    async def get_formatter_diff(self) -> Optional[str]:
        """Get the diff created by formatters."""
        if not self.original_contents:
            return None

        formatter_changes = []

        for file_path, original in self.original_contents.items():
            if file_path.exists():
                current = file_path.read_text()
                if current != original:
                    # Generate diff for formatter changes
                    relative_path = file_path.relative_to(self.working_dir)
                    diff_lines = difflib.unified_diff(
                        original.splitlines(keepends=True),
                        current.splitlines(keepends=True),
                        fromfile=str(relative_path),
                        tofile=str(relative_path),
                        n=3
                    )
                    formatter_changes.extend(diff_lines)

        if formatter_changes:
            self.formatter_diff = ''.join(formatter_changes)
            return self.formatter_diff

        return None

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute hash of file content."""
        content = file_path.read_text()
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def rollback(self) -> None:
        """Rollback changes to original state."""
        for file_path, original_content in self.original_contents.items():
            try:
                file_path.write_text(original_content)
                logger.info(f"Rolled back {file_path}")
            except Exception as e:
                logger.error(f"Failed to rollback {file_path}: {e}")

        self.original_contents.clear()

    def create_minimal_reject_context(self, reject: RejectInfo) -> str:
        """Create minimal context for a rejected hunk."""
        lines = [
            f"Rejected hunk in {reject.file} (hunk #{reject.hunk_index + 1})",
            f"Reason: {reject.reason}",
            "",
            "Expected context:",
            "```"
        ]
        lines.extend(reject.expected_context[:5])  # First 5 lines
        lines.append("```")
        lines.append("")
        lines.append("Actual context found:")
        lines.append("```")
        lines.extend(reject.actual_context[:5])  # First 5 lines
        lines.append("```")

        return '\n'.join(lines)