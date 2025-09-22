"""Test Runner with targeted test selection."""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    duration: float
    file: Optional[str] = None
    line: Optional[int] = None
    failure_message: Optional[str] = None
    stack_trace: Optional[str] = None


@dataclass
class TestReport:
    """Complete test execution report."""
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    skipped_count: int
    duration: float
    test_results: List[TestResult] = field(default_factory=list)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class TestRunner:
    """Runner for executing tests with targeting capabilities."""

    def __init__(self, working_dir: Path, context_engine=None):
        self.working_dir = working_dir
        self.context_engine = context_engine

        # Test framework detection patterns
        self.test_patterns = {
            'python': {
                'pytest': {
                    'config_files': ['pytest.ini', 'pyproject.toml', 'setup.cfg'],
                    'test_pattern': 'test_*.py',
                    'command': 'pytest',
                    'args': ['-v', '--json-report', '--json-report-file=.test_report.json']
                },
                'unittest': {
                    'config_files': [],
                    'test_pattern': 'test_*.py',
                    'command': 'python -m unittest',
                    'args': ['-v']
                }
            },
            'javascript': {
                'jest': {
                    'config_files': ['jest.config.js', 'jest.config.json'],
                    'test_pattern': '*.test.js',
                    'command': 'jest',
                    'args': ['--json', '--outputFile=.test_report.json']
                },
                'mocha': {
                    'config_files': ['.mocharc.js', '.mocharc.json'],
                    'test_pattern': '*.spec.js',
                    'command': 'mocha',
                    'args': ['--reporter', 'json']
                }
            },
            'typescript': {
                'jest': {
                    'config_files': ['jest.config.js', 'jest.config.ts'],
                    'test_pattern': '*.test.ts',
                    'command': 'jest',
                    'args': ['--json', '--outputFile=.test_report.json']
                }
            },
            'rust': {
                'cargo': {
                    'config_files': ['Cargo.toml'],
                    'test_pattern': '',
                    'command': 'cargo test',
                    'args': ['--', '--format', 'json']
                }
            },
            'go': {
                'go': {
                    'config_files': ['go.mod'],
                    'test_pattern': '',
                    'command': 'go test',
                    'args': ['-json', './...']
                }
            }
        }

        self.test_framework = None
        self.test_command = None

    async def detect_test_framework(self) -> Optional[Dict[str, Any]]:
        """Detect the test framework used in the project."""
        # Check for language-specific config files
        for language, frameworks in self.test_patterns.items():
            for framework_name, framework_config in frameworks.items():
                for config_file in framework_config['config_files']:
                    if (self.working_dir / config_file).exists():
                        self.test_framework = framework_name
                        self.test_command = framework_config['command']
                        return {
                            'language': language,
                            'framework': framework_name,
                            'command': framework_config['command'],
                            'args': framework_config['args']
                        }

        # Fallback: detect by file patterns
        if list(self.working_dir.rglob('test_*.py')):
            self.test_framework = 'pytest'
            self.test_command = 'pytest'
            return {
                'language': 'python',
                'framework': 'pytest',
                'command': 'pytest',
                'args': ['-v']
            }

        if list(self.working_dir.rglob('*.test.js')):
            self.test_framework = 'jest'
            self.test_command = 'jest'
            return {
                'language': 'javascript',
                'framework': 'jest',
                'command': 'jest',
                'args': []
            }

        return None

    async def run_targeted(self, impacted: Dict[str, Any]) -> TestReport:
        """Run tests targeting specific changed symbols and files."""
        framework = await self.detect_test_framework()
        if not framework:
            logger.warning("Could not detect test framework")
            return TestReport(
                passed=False,
                total=0,
                passed_count=0,
                failed_count=0,
                skipped_count=0,
                duration=0.0,
                failures=[{'reason': 'No test framework detected'}]
            )

        # Find tests related to impacted code
        targeted_tests = await self._find_targeted_tests(impacted)

        if not targeted_tests:
            logger.info("No targeted tests found, running all tests")
            return await self.run_full()

        logger.info(f"Running {len(targeted_tests)} targeted tests")

        # Build test command for targeted tests
        command = self._build_test_command(framework, targeted_tests)

        # Execute tests
        return await self._execute_tests(command, is_targeted=True)

    async def run_full(self) -> TestReport:
        """Run the full test suite."""
        framework = await self.detect_test_framework()
        if not framework:
            return TestReport(
                passed=False,
                total=0,
                passed_count=0,
                failed_count=0,
                skipped_count=0,
                duration=0.0,
                failures=[{'reason': 'No test framework detected'}]
            )

        # Build command for full test run
        command = self._build_test_command(framework)

        # Execute tests
        return await self._execute_tests(command, is_targeted=False)

    async def _find_targeted_tests(self, impacted: Dict[str, Any]) -> List[str]:
        """Find tests that should run based on impacted code."""
        targeted = set()

        # Get test files from impacted analysis
        if 'tests' in impacted:
            targeted.update(impacted['tests'])

        # Find tests by naming convention
        for file_path in impacted.get('files', []):
            path = Path(file_path)
            base_name = path.stem

            # Common test file patterns
            test_patterns = [
                f"test_{base_name}.py",
                f"{base_name}_test.py",
                f"{base_name}.test.js",
                f"{base_name}.spec.js",
                f"{base_name}_test.go"
            ]

            for pattern in test_patterns:
                for test_file in self.working_dir.rglob(pattern):
                    targeted.add(str(test_file.relative_to(self.working_dir)))

        # Find tests by symbol references
        if self.context_engine:
            for symbol_info in impacted.get('symbols', []):
                symbol_name = symbol_info['name']
                # Look for test files that reference this symbol
                for test_file in self.working_dir.rglob('test_*.py'):
                    try:
                        content = test_file.read_text()
                        if symbol_name in content:
                            targeted.add(str(test_file.relative_to(self.working_dir)))
                    except Exception:
                        pass

        return list(targeted)

    def _build_test_command(
        self,
        framework: Dict[str, Any],
        targeted_tests: Optional[List[str]] = None
    ) -> str:
        """Build the test execution command."""
        base_command = framework['command']
        args = framework.get('args', [])

        if targeted_tests:
            # Framework-specific targeted test execution
            if framework['framework'] == 'pytest':
                command_parts = [base_command] + args + targeted_tests
            elif framework['framework'] == 'jest':
                # Jest uses testPathPattern
                pattern = '|'.join(re.escape(test) for test in targeted_tests)
                command_parts = [base_command] + args + [f'--testPathPattern="{pattern}"']
            elif framework['framework'] == 'go':
                # Go test with specific packages
                packages = set(str(Path(test).parent) for test in targeted_tests)
                command_parts = ['go', 'test'] + args + list(packages)
            else:
                # Generic: just append test files
                command_parts = [base_command] + args + targeted_tests
        else:
            # Full test suite
            command_parts = [base_command] + args

        return ' '.join(command_parts)

    async def _execute_tests(self, command: str, is_targeted: bool) -> TestReport:
        """Execute test command and parse results."""
        start_time = datetime.now()

        try:
            # Run tests
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Parse output based on test framework
            report = await self._parse_test_output(
                result.stdout,
                result.stderr,
                result.returncode,
                duration,
                command
            )

            report.command = command
            return report

        except subprocess.TimeoutExpired:
            return TestReport(
                passed=False,
                total=0,
                passed_count=0,
                failed_count=0,
                skipped_count=0,
                duration=300.0,
                failures=[{'reason': 'Test execution timeout'}],
                command=command
            )
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return TestReport(
                passed=False,
                total=0,
                passed_count=0,
                failed_count=0,
                skipped_count=0,
                duration=0.0,
                failures=[{'reason': f'Test execution error: {str(e)}'}],
                command=command
            )

    async def _parse_test_output(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        duration: float,
        command: str
    ) -> TestReport:
        """Parse test output into structured report."""
        report = TestReport(
            passed=returncode == 0,
            total=0,
            passed_count=0,
            failed_count=0,
            skipped_count=0,
            duration=duration,
            stdout=stdout,
            stderr=stderr
        )

        # Try to parse structured output (JSON)
        json_report_file = self.working_dir / '.test_report.json'
        if json_report_file.exists():
            try:
                with open(json_report_file, 'r') as f:
                    json_data = json.load(f)
                    report = self._parse_json_report(json_data, report)
                json_report_file.unlink()  # Clean up
                return report
            except Exception as e:
                logger.debug(f"Failed to parse JSON test report: {e}")

        # Fallback: parse text output
        if self.test_framework == 'pytest':
            report = self._parse_pytest_output(stdout, report)
        elif self.test_framework == 'jest':
            report = self._parse_jest_output(stdout, report)
        elif self.test_framework == 'go':
            report = self._parse_go_test_output(stdout, report)
        else:
            # Generic parsing
            report = self._parse_generic_output(stdout, stderr, returncode, report)

        return report

    def _parse_pytest_output(self, output: str, report: TestReport) -> TestReport:
        """Parse pytest text output."""
        lines = output.split('\n')

        # Parse summary line (e.g., "===== 3 passed, 1 failed in 0.12s =====")
        summary_pattern = r'=+\s*(\d+)\s+passed(?:,\s*(\d+)\s+failed)?(?:,\s*(\d+)\s+skipped)?.*=+'
        for line in lines:
            match = re.search(summary_pattern, line)
            if match:
                report.passed_count = int(match.group(1) or 0)
                report.failed_count = int(match.group(2) or 0)
                report.skipped_count = int(match.group(3) or 0)
                report.total = report.passed_count + report.failed_count + report.skipped_count
                break

        # Parse failures
        in_failure = False
        current_failure = {}
        for line in lines:
            if line.startswith('FAILED '):
                in_failure = True
                # Extract test name
                match = re.match(r'FAILED (.*?)(?:\[.*?\])? - (.*)', line)
                if match:
                    current_failure = {
                        'test': match.group(1),
                        'message': match.group(2)
                    }
            elif in_failure and line.startswith('_'):
                # End of failure section
                if current_failure:
                    report.failures.append(current_failure)
                    current_failure = {}
                in_failure = False

        return report

    def _parse_jest_output(self, output: str, report: TestReport) -> TestReport:
        """Parse Jest text output."""
        # Try to parse JSON output first
        try:
            json_match = re.search(r'\{.*"testResults".*\}', output, re.DOTALL)
            if json_match:
                json_data = json.loads(json_match.group())
                return self._parse_json_report(json_data, report)
        except Exception:
            pass

        # Fallback to text parsing
        lines = output.split('\n')
        for line in lines:
            if 'Tests:' in line:
                # Parse summary line
                match = re.search(r'(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?', line)
                if match:
                    report.passed_count = int(match.group(1) or 0)
                    report.failed_count = int(match.group(2) or 0)
                    report.skipped_count = int(match.group(3) or 0)
                    report.total = report.passed_count + report.failed_count + report.skipped_count

        return report

    def _parse_go_test_output(self, output: str, report: TestReport) -> TestReport:
        """Parse Go test JSON output."""
        lines = output.split('\n')
        test_results = {}

        for line in lines:
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                if event.get('Action') == 'pass':
                    report.passed_count += 1
                    test_results[event['Test']] = TestResult(
                        name=event['Test'],
                        status='passed',
                        duration=event.get('Elapsed', 0)
                    )
                elif event.get('Action') == 'fail':
                    report.failed_count += 1
                    test_results[event['Test']] = TestResult(
                        name=event['Test'],
                        status='failed',
                        duration=event.get('Elapsed', 0)
                    )
                    report.failures.append({
                        'test': event['Test'],
                        'package': event.get('Package', '')
                    })
            except json.JSONDecodeError:
                # Not JSON, skip
                pass

        report.total = report.passed_count + report.failed_count
        report.test_results = list(test_results.values())

        return report

    def _parse_json_report(self, json_data: Dict, report: TestReport) -> TestReport:
        """Parse structured JSON test report."""
        # Jest format
        if 'testResults' in json_data:
            for test_file in json_data['testResults']:
                for test in test_file.get('assertionResults', []):
                    result = TestResult(
                        name=test['title'],
                        status='passed' if test['status'] == 'passed' else 'failed',
                        duration=0,
                        file=test_file['name']
                    )
                    report.test_results.append(result)

                    if test['status'] == 'passed':
                        report.passed_count += 1
                    else:
                        report.failed_count += 1
                        report.failures.append({
                            'test': test['title'],
                            'file': test_file['name'],
                            'message': ' '.join(test.get('failureMessages', []))
                        })

        # Pytest JSON report format
        elif 'tests' in json_data:
            for test in json_data['tests']:
                result = TestResult(
                    name=test['nodeid'],
                    status='passed' if test['outcome'] == 'passed' else 'failed',
                    duration=test.get('duration', 0)
                )
                report.test_results.append(result)

                if test['outcome'] == 'passed':
                    report.passed_count += 1
                else:
                    report.failed_count += 1
                    report.failures.append({
                        'test': test['nodeid'],
                        'message': test.get('call', {}).get('longrepr', '')
                    })

        report.total = report.passed_count + report.failed_count + report.skipped_count

        return report

    def _parse_generic_output(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        report: TestReport
    ) -> TestReport:
        """Generic test output parsing."""
        # Look for common patterns
        if returncode == 0:
            report.passed = True
            # Try to find test count
            match = re.search(r'(\d+) test[s]? passed', stdout.lower())
            if match:
                report.passed_count = int(match.group(1))
                report.total = report.passed_count
        else:
            report.passed = False
            # Look for failure indicators
            if 'FAILED' in stdout or 'FAIL' in stdout:
                report.failed_count = stdout.count('FAILED') + stdout.count('FAIL')
                report.total = report.failed_count

            # Extract first failure
            for line in stdout.split('\n'):
                if 'FAILED' in line or 'FAIL' in line or 'Error' in line:
                    report.failures.append({
                        'message': line.strip()
                    })
                    break

        return report

    def extract_minimal_failure(self, report: TestReport) -> Dict[str, Any]:
        """Extract minimal failure information for repair."""
        if not report.failures:
            return {}

        first_failure = report.failures[0]

        # Find the actual error in stdout/stderr
        error_context = []
        if first_failure.get('test'):
            test_name = first_failure['test']
            # Find lines around the test failure
            for output in [report.stdout, report.stderr]:
                lines = output.split('\n')
                for i, line in enumerate(lines):
                    if test_name in line:
                        # Get surrounding lines
                        start = max(0, i - 3)
                        end = min(len(lines), i + 10)
                        error_context = lines[start:end]
                        break

        return {
            'test_name': first_failure.get('test', 'unknown'),
            'message': first_failure.get('message', ''),
            'file': first_failure.get('file', ''),
            'context': '\n'.join(error_context) if error_context else report.stderr[:500],
            'total_failures': len(report.failures)
        }