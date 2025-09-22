"""Policy Engine for safety validation and constraints."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class PolicyResult:
    """Result of policy validation."""
    is_valid: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class PolicyConfig:
    """Configuration for policy rules."""
    # File path rules
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)

    # Content rules
    forbidden_patterns: List[str] = field(default_factory=list)
    required_patterns: List[str] = field(default_factory=list)

    # Dependency rules
    allowed_dependencies: List[str] = field(default_factory=list)
    forbidden_dependencies: List[str] = field(default_factory=list)

    # Size limits
    max_file_size: int = 1_000_000  # 1MB
    max_diff_size: int = 10_000  # lines
    max_files_changed: int = 50

    # Security rules
    forbid_credentials: bool = True
    forbid_telemetry: bool = True
    forbid_license_changes: bool = True

    # Language constraints
    allowed_languages: List[str] = field(default_factory=list)
    forbidden_languages: List[str] = field(default_factory=list)


class PolicyEngine:
    """Engine for validating changes against security and safety policies."""

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()

        # Compile regex patterns for efficiency
        self.forbidden_regex = [
            re.compile(pattern) for pattern in self.config.forbidden_patterns
        ]
        self.required_regex = [
            re.compile(pattern) for pattern in self.config.required_patterns
        ]

        # Security patterns
        self.credential_patterns = [
            re.compile(r'(?i)(api[_-]?key|api[_-]?secret|access[_-]?token|auth[_-]?token|private[_-]?key|secret[_-]?key)\s*[=:]\s*["\'][\w\-]+["\']'),
            re.compile(r'(?i)bearer\s+[\w\-\.]+'),
            re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'),
            re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']+["\']'),
            re.compile(r'(?i)aws[_-]?(access[_-]?key[_-]?id|secret[_-]?access[_-]?key|session[_-]?token)'),
        ]

        self.telemetry_patterns = [
            re.compile(r'(?i)(analytics|telemetry|tracking|metrics)\.'),
            re.compile(r'(?i)(google[_-]?analytics|mixpanel|segment|amplitude|datadog)'),
            re.compile(r'(?i)track(Event|User|Page|Action)'),
        ]

        self.license_patterns = [
            re.compile(r'(?i)licen[cs]e'),
            re.compile(r'(?i)copyright'),
            re.compile(r'(?i)(mit|apache|gpl|bsd|proprietary)\s+licen[cs]e'),
        ]

        # Common sensitive file patterns
        self.sensitive_files = {
            '.env', '.env.local', '.env.production',
            'config.json', 'settings.json',
            'credentials', 'secrets',
            '.git/config', '.ssh/',
            '*.pem', '*.key', '*.cert',
            '.aws/', '.gcp/', '.azure/'
        }

    async def validate_plan(self, plan: Dict[str, Any]) -> PolicyResult:
        """Validate a task plan against policies."""
        result = PolicyResult(is_valid=True)

        # Check file targets
        if 'files' in plan:
            for file_path in plan['files']:
                if not self._is_path_allowed(file_path):
                    result.is_valid = False
                    result.violations.append(f"File path not allowed: {file_path}")

        # Check operation types
        if 'operations' in plan:
            for op in plan['operations']:
                if op.get('type') == 'delete' and op.get('target') in self.sensitive_files:
                    result.is_valid = False
                    result.violations.append(f"Cannot delete sensitive file: {op['target']}")

        # Check for dependency changes
        if 'dependencies' in plan:
            for dep in plan.get('dependencies', {}).get('add', []):
                if not self._is_dependency_allowed(dep):
                    result.is_valid = False
                    result.violations.append(f"Dependency not allowed: {dep}")

        # Warn about large scope
        if 'estimated_changes' in plan:
            if plan['estimated_changes'] > 1000:
                result.warnings.append(f"Large change scope: {plan['estimated_changes']} estimated changes")

        if result.violations:
            result.reasons = result.violations

        return result

    async def validate_diff(self, diff: str) -> PolicyResult:
        """Validate a unified diff against policies."""
        result = PolicyResult(is_valid=True)

        # Parse diff to extract changes
        file_changes = self._parse_diff(diff)

        # Check number of files
        if len(file_changes) > self.config.max_files_changed:
            result.warnings.append(f"Too many files changed: {len(file_changes)} > {self.config.max_files_changed}")

        # Check each file
        for file_info in file_changes:
            file_path = file_info['path']

            # Check path permissions
            if not self._is_path_allowed(file_path):
                result.is_valid = False
                result.violations.append(f"File path not allowed: {file_path}")

            # Check for sensitive file modifications
            if self._is_sensitive_file(file_path):
                result.warnings.append(f"Modifying sensitive file: {file_path}")

            # Check content changes
            for line in file_info.get('additions', []):
                # Check for credentials
                if self.config.forbid_credentials:
                    for pattern in self.credential_patterns:
                        if pattern.search(line):
                            result.is_valid = False
                            result.violations.append(f"Potential credential in diff: {file_path}")
                            break

                # Check for telemetry
                if self.config.forbid_telemetry:
                    for pattern in self.telemetry_patterns:
                        if pattern.search(line):
                            result.warnings.append(f"Potential telemetry code in: {file_path}")
                            break

                # Check for forbidden patterns
                for pattern in self.forbidden_regex:
                    if pattern.search(line):
                        result.is_valid = False
                        result.violations.append(f"Forbidden pattern found in {file_path}")
                        break

            # Check for dependency changes
            if file_path in ['package.json', 'requirements.txt', 'Cargo.toml', 'go.mod']:
                dep_result = self._validate_dependency_changes(file_info)
                if not dep_result.is_valid:
                    result.is_valid = False
                    result.violations.extend(dep_result.violations)

            # Check for license changes
            if self.config.forbid_license_changes:
                if self._contains_license_change(file_info):
                    result.is_valid = False
                    result.violations.append(f"License change detected in {file_path}")

        # Check diff size
        total_lines = sum(
            len(f.get('additions', [])) + len(f.get('deletions', []))
            for f in file_changes
        )
        if total_lines > self.config.max_diff_size:
            result.warnings.append(f"Large diff: {total_lines} lines > {self.config.max_diff_size}")

        if result.violations:
            result.reasons = result.violations

        return result

    async def validate_commands(self, commands: List[Dict[str, Any]]) -> PolicyResult:
        """Validate commands to be executed."""
        result = PolicyResult(is_valid=True)

        dangerous_commands = [
            'rm -rf', 'sudo', 'chmod 777', 'curl | sh', 'wget | sh',
            'pip install --user', 'npm install -g', 'cargo install',
            'git push', 'git commit', 'git merge',
            'docker', 'kubectl', 'terraform',
            'aws', 'gcloud', 'az'
        ]

        for cmd_info in commands:
            cmd = cmd_info.get('command', '')

            # Check for dangerous commands
            for dangerous in dangerous_commands:
                if dangerous in cmd:
                    result.warnings.append(f"Potentially dangerous command: {cmd[:50]}...")

            # Check for network operations
            if any(net_cmd in cmd for net_cmd in ['curl', 'wget', 'nc', 'telnet', 'ssh']):
                result.warnings.append(f"Network operation in command: {cmd[:50]}...")

            # Check for privilege escalation
            if 'sudo' in cmd or 'su ' in cmd:
                result.is_valid = False
                result.violations.append(f"Privilege escalation not allowed: {cmd[:50]}...")

            # Check for system modifications
            if any(sys_cmd in cmd for sys_cmd in ['systemctl', 'service', 'launchctl', 'init.d']):
                result.is_valid = False
                result.violations.append(f"System modification not allowed: {cmd[:50]}...")

        if result.violations:
            result.reasons = result.violations

        return result

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a file path is allowed by policy."""
        path = Path(path)

        # Check denied paths
        for denied in self.config.denied_paths:
            if path.match(denied):
                return False

        # Check allowed paths (if specified, only these are allowed)
        if self.config.allowed_paths:
            for allowed in self.config.allowed_paths:
                if path.match(allowed):
                    return True
            return False  # Not in allowed list

        # Default allow if no specific rules
        return True

    def _is_sensitive_file(self, file_path: str) -> bool:
        """Check if a file is sensitive."""
        path = Path(file_path)
        name = path.name.lower()

        for pattern in self.sensitive_files:
            if '*' in pattern:
                if path.match(pattern):
                    return True
            elif pattern in str(path):
                return True

        return name in self.sensitive_files

    def _is_dependency_allowed(self, dependency: str) -> bool:
        """Check if a dependency is allowed."""
        # Extract package name (handle version specs)
        package = re.split(r'[@=<>~^]', dependency)[0].strip()

        # Check forbidden dependencies
        if package in self.config.forbidden_dependencies:
            return False

        # Check allowed dependencies (if specified, only these are allowed)
        if self.config.allowed_dependencies:
            return package in self.config.allowed_dependencies

        # Check for suspicious packages
        suspicious_patterns = [
            r'test', r'debug', r'hack', r'exploit', r'backdoor',
            r'malware', r'virus', r'trojan', r'rootkit'
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, package, re.IGNORECASE):
                return False

        return True

    def _parse_diff(self, diff: str) -> List[Dict[str, Any]]:
        """Parse unified diff into structured format."""
        file_changes = []
        current_file = None
        current_changes = {'additions': [], 'deletions': []}

        for line in diff.split('\n'):
            if line.startswith('--- '):
                if current_file:
                    file_changes.append({
                        'path': current_file,
                        **current_changes
                    })
                current_file = line[4:].split('\t')[0]
                current_changes = {'additions': [], 'deletions': []}

            elif line.startswith('+++ '):
                current_file = line[4:].split('\t')[0]

            elif line.startswith('+') and not line.startswith('+++'):
                current_changes['additions'].append(line[1:])

            elif line.startswith('-') and not line.startswith('---'):
                current_changes['deletions'].append(line[1:])

        # Add last file
        if current_file:
            file_changes.append({
                'path': current_file,
                **current_changes
            })

        return file_changes

    def _validate_dependency_changes(self, file_info: Dict[str, Any]) -> PolicyResult:
        """Validate dependency file changes."""
        result = PolicyResult(is_valid=True)

        # Look for new dependencies in additions
        for line in file_info.get('additions', []):
            # Simple pattern matching for common dependency formats
            dep_patterns = [
                r'"([^"]+)":\s*"[^"]+"',  # package.json
                r'([^\s=<>~]+)[=<>~]',    # requirements.txt
                r'([^\s]+)\s*=',          # Cargo.toml
                r'require\s+([^\s]+)',    # go.mod
            ]

            for pattern in dep_patterns:
                match = re.search(pattern, line)
                if match:
                    dep_name = match.group(1)
                    if not self._is_dependency_allowed(dep_name):
                        result.is_valid = False
                        result.violations.append(f"Forbidden dependency: {dep_name}")

        return result

    def _contains_license_change(self, file_info: Dict[str, Any]) -> bool:
        """Check if file changes contain license modifications."""
        all_changes = file_info.get('additions', []) + file_info.get('deletions', [])

        for line in all_changes:
            for pattern in self.license_patterns:
                if pattern.search(line):
                    return True

        # Special check for LICENSE file
        if 'license' in file_info['path'].lower():
            return True

        return False

    def create_policy_report(self, results: List[PolicyResult]) -> str:
        """Create a human-readable policy report."""
        report_lines = ["Policy Validation Report", "=" * 50, ""]

        total_violations = sum(len(r.violations) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)

        report_lines.append(f"Total Violations: {total_violations}")
        report_lines.append(f"Total Warnings: {total_warnings}")
        report_lines.append("")

        if total_violations > 0:
            report_lines.append("VIOLATIONS (must fix):")
            for i, result in enumerate(results, 1):
                if result.violations:
                    report_lines.append(f"\n  Check #{i}:")
                    for violation in result.violations:
                        report_lines.append(f"    ❌ {violation}")

        if total_warnings > 0:
            report_lines.append("\nWARNINGS (review recommended):")
            for i, result in enumerate(results, 1):
                if result.warnings:
                    report_lines.append(f"\n  Check #{i}:")
                    for warning in result.warnings:
                        report_lines.append(f"    ⚠️  {warning}")

        return '\n'.join(report_lines)