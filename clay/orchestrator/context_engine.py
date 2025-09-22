"""Context Engine for intelligent code analysis and retrieval."""

import hashlib
import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class FileContext:
    """Represents a file with its context."""
    path: Path
    content: str
    hash: str
    language: str
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    symbols: List['Symbol'] = field(default_factory=list)
    test_refs: List[str] = field(default_factory=list)


@dataclass
class Symbol:
    """Represents a code symbol (function, class, etc.)."""
    name: str
    type: str  # 'function', 'class', 'method', 'variable'
    file_path: Path
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    references: List[Tuple[Path, int]] = field(default_factory=list)
    test_coverage: List[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """Result of context retrieval."""
    files: List[Dict[str, Any]]
    symbols: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    configs: List[str] = field(default_factory=list)
    guides: List[str] = field(default_factory=list)
    token_count: int = 0


class ContextEngine:
    """Engine for analyzing and retrieving relevant code context."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.file_index: Dict[Path, FileContext] = {}
        self.symbol_index: Dict[str, List[Symbol]] = defaultdict(list)
        self.import_graph: Dict[Path, Set[Path]] = defaultdict(set)
        self.test_mapping: Dict[Path, Set[Path]] = defaultdict(set)

        # Configuration patterns
        self.config_patterns = {
            'python': ['setup.py', 'pyproject.toml', 'requirements*.txt'],
            'javascript': ['package.json', 'tsconfig.json', '*.config.js'],
            'rust': ['Cargo.toml'],
            'go': ['go.mod', 'go.sum']
        }

        self.guide_patterns = [
            'README*', 'CONTRIBUTING*', 'AGENT.md', 'DEVELOPMENT*', '.claude*'
        ]

    async def index_repository(self, path: Optional[Path] = None) -> None:
        """Index the repository for symbols, imports, and relationships."""
        root = path or self.project_root
        logger.info(f"Indexing repository at {root}")

        # First pass: index all files
        for file_path in root.rglob("*"):
            if file_path.is_file() and self._should_index(file_path):
                await self._index_file(file_path)

        # Second pass: build relationships
        self._build_import_graph()
        self._map_tests_to_sources()

        logger.info(f"Indexed {len(self.file_index)} files, {len(self.symbol_index)} symbols")

    async def retrieve(self, goal: str, budget_tokens: int) -> RetrievalResult:
        """Retrieve relevant context for a goal within token budget."""
        logger.info(f"Retrieving context for goal: {goal[:100]}...")

        # Parse goal to identify key terms and potential files
        key_terms = self._extract_key_terms(goal)
        mentioned_files = self._extract_file_mentions(goal)

        # Score and rank files
        file_scores = {}
        for path, context in self.file_index.items():
            score = self._score_file(context, key_terms, mentioned_files)
            if score > 0:
                file_scores[path] = score

        # Sort by relevance
        sorted_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)

        # Build result within budget
        result = RetrievalResult(
            files=[],
            symbols=[],
            imports=[],
            tests=[],
            configs=[],
            guides=[],
            token_count=0
        )

        for file_path, score in sorted_files:
            context = self.file_index[file_path]
            file_info = self._build_file_info(context, key_terms)

            # Estimate tokens (rough: 1 token per 4 chars)
            estimated_tokens = len(file_info.get('content', '')) // 4

            if result.token_count + estimated_tokens > budget_tokens:
                # Add just the path and key ranges if over budget
                file_info = {
                    'path': str(file_path),
                    'hash': context.hash,
                    'relevant_ranges': self._find_relevant_ranges(context, key_terms)
                }
                result.files.append(file_info)
                break

            result.files.append(file_info)
            result.token_count += estimated_tokens

            # Add symbols from this file
            for symbol in context.symbols:
                if any(term.lower() in symbol.name.lower() for term in key_terms):
                    result.symbols.append({
                        'name': symbol.name,
                        'type': symbol.type,
                        'file': str(symbol.file_path),
                        'signature': symbol.signature
                    })

            # Add imports from this file
            result.imports.extend(context.imports)

            # Add related tests
            if file_path in self.test_mapping:
                for test_path in self.test_mapping[file_path]:
                    if str(test_path) not in result.tests:
                        result.tests.append(str(test_path))

        # Add configs and guides
        result.configs = self._find_configs()
        result.guides = self._find_guides()

        return result

    async def analyze_changes(self, diff: str) -> Dict[str, Any]:
        """Analyze a diff to identify impacted symbols and files."""
        impacted = {
            'files': [],
            'symbols': [],
            'tests': []
        }

        # Parse unified diff
        file_changes = self._parse_unified_diff(diff)

        for file_path, changes in file_changes.items():
            path = self.project_root / file_path

            if path not in self.file_index:
                continue

            context = self.file_index[path]
            impacted['files'].append(str(file_path))

            # Find impacted symbols
            for symbol in context.symbols:
                for line_num in changes['modified_lines']:
                    if symbol.line_start <= line_num <= symbol.line_end:
                        impacted['symbols'].append({
                            'name': symbol.name,
                            'type': symbol.type,
                            'file': str(file_path)
                        })

            # Find related tests
            if path in self.test_mapping:
                for test_path in self.test_mapping[path]:
                    impacted['tests'].append(str(test_path))

        return impacted

    async def _index_file(self, file_path: Path) -> None:
        """Index a single file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            file_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            language = self._detect_language(file_path)

            context = FileContext(
                path=file_path,
                content=content,
                hash=file_hash,
                language=language
            )

            if language == 'python':
                self._index_python_file(context)
            elif language in ['javascript', 'typescript']:
                self._index_javascript_file(context)
            # Add more language parsers as needed

            self.file_index[file_path] = context

            # Update symbol index
            for symbol in context.symbols:
                self.symbol_index[symbol.name].append(symbol)

        except Exception as e:
            logger.debug(f"Failed to index {file_path}: {e}")

    def _index_python_file(self, context: FileContext) -> None:
        """Index a Python file for symbols and imports."""
        try:
            tree = ast.parse(context.content)

            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        context.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        context.imports.append(f"{module}.{alias.name}")

            # Extract symbols
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbol = Symbol(
                        name=node.name,
                        type='function',
                        file_path=context.path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        signature=self._get_function_signature(node),
                        docstring=ast.get_docstring(node)
                    )
                    context.symbols.append(symbol)

                elif isinstance(node, ast.ClassDef):
                    symbol = Symbol(
                        name=node.name,
                        type='class',
                        file_path=context.path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        docstring=ast.get_docstring(node)
                    )
                    context.symbols.append(symbol)

                    # Add methods
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_symbol = Symbol(
                                name=f"{node.name}.{item.name}",
                                type='method',
                                file_path=context.path,
                                line_start=item.lineno,
                                line_end=item.end_lineno or item.lineno,
                                signature=self._get_function_signature(item),
                                docstring=ast.get_docstring(item)
                            )
                            context.symbols.append(method_symbol)

        except SyntaxError as e:
            logger.debug(f"Syntax error in {context.path}: {e}")

    def _index_javascript_file(self, context: FileContext) -> None:
        """Index JavaScript/TypeScript file (simplified)."""
        # Use regex for basic parsing
        content = context.content

        # Find imports
        import_pattern = r'import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            context.imports.append(match.group(1))

        # Find function declarations
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)'
        for match in re.finditer(func_pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            symbol = Symbol(
                name=match.group(1),
                type='function',
                file_path=context.path,
                line_start=line_num,
                line_end=line_num  # Simplified
            )
            context.symbols.append(symbol)

        # Find class declarations
        class_pattern = r'(?:export\s+)?class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            symbol = Symbol(
                name=match.group(1),
                type='class',
                file_path=context.path,
                line_start=line_num,
                line_end=line_num  # Simplified
            )
            context.symbols.append(symbol)

    def _build_import_graph(self) -> None:
        """Build the import dependency graph."""
        for path, context in self.file_index.items():
            for import_name in context.imports:
                # Try to resolve import to a file
                resolved = self._resolve_import(path, import_name)
                if resolved and resolved in self.file_index:
                    self.import_graph[path].add(resolved)

    def _map_tests_to_sources(self) -> None:
        """Map test files to their source files."""
        for path, context in self.file_index.items():
            if self._is_test_file(path):
                # Find what this test is testing
                for import_name in context.imports:
                    resolved = self._resolve_import(path, import_name)
                    if resolved and not self._is_test_file(resolved):
                        self.test_mapping[resolved].add(path)

    def _should_index(self, file_path: Path) -> bool:
        """Check if a file should be indexed."""
        # Skip hidden files and directories
        if any(part.startswith('.') for part in file_path.parts):
            return False

        # Skip common non-code files
        skip_extensions = {'.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe', '.jpg', '.png', '.gif'}
        if file_path.suffix in skip_extensions:
            return False

        # Skip node_modules, venv, etc.
        skip_dirs = {'node_modules', 'venv', 'env', '__pycache__', 'dist', 'build'}
        if any(part in skip_dirs for part in file_path.parts):
            return False

        return True

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.md': 'markdown',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.json': 'json',
            '.toml': 'toml'
        }
        return ext_to_lang.get(file_path.suffix, 'unknown')

    def _is_test_file(self, file_path: Path) -> bool:
        """Check if a file is a test file."""
        name = file_path.name.lower()
        return (
            'test' in name or
            'spec' in name or
            file_path.parts[-2:] == ('tests',) or
            file_path.parts[-2:] == ('test',)
        )

    def _extract_key_terms(self, goal: str) -> List[str]:
        """Extract key terms from the goal."""
        # Simple tokenization and filtering
        words = re.findall(r'\b\w+\b', goal.lower())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'been'}
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _extract_file_mentions(self, goal: str) -> List[str]:
        """Extract file paths mentioned in the goal."""
        # Look for file-like patterns
        patterns = [
            r'[\'"`]([^\'"`]+\.\w+)[\'"`]',  # Quoted filenames
            r'\b(\w+\.\w+)\b',  # Unquoted filenames
            r'(?:file|module|class)\s+(\w+)',  # References to files/modules
        ]

        mentions = []
        for pattern in patterns:
            mentions.extend(re.findall(pattern, goal))

        return mentions

    def _score_file(self, context: FileContext, key_terms: List[str], mentioned_files: List[str]) -> float:
        """Score a file's relevance to the goal."""
        score = 0.0

        # Direct file mention
        file_name = context.path.name
        if any(mention in file_name for mention in mentioned_files):
            score += 10.0

        # Key terms in file name
        for term in key_terms:
            if term in file_name.lower():
                score += 2.0

        # Key terms in content (weighted by location)
        content_lower = context.content.lower()
        for term in key_terms:
            count = content_lower.count(term)
            if count > 0:
                score += min(count * 0.5, 5.0)

        # Symbol matches
        for symbol in context.symbols:
            for term in key_terms:
                if term in symbol.name.lower():
                    score += 3.0
                if symbol.docstring and term in symbol.docstring.lower():
                    score += 1.0

        # Import graph proximity (files that import or are imported by mentioned files)
        if context.path in self.import_graph:
            for imported in self.import_graph[context.path]:
                if any(mention in imported.name for mention in mentioned_files):
                    score += 1.5

        return score

    def _build_file_info(self, context: FileContext, key_terms: List[str]) -> Dict[str, Any]:
        """Build file information dictionary."""
        # Find relevant ranges
        ranges = self._find_relevant_ranges(context, key_terms)

        return {
            'path': str(context.path.relative_to(self.project_root)),
            'hash': context.hash,
            'language': context.language,
            'symbols': [
                {
                    'name': s.name,
                    'type': s.type,
                    'line_start': s.line_start,
                    'line_end': s.line_end
                }
                for s in context.symbols
            ],
            'imports': context.imports[:10],  # Limit imports
            'ranges': ranges,
            'content': context.content if len(ranges) > 0 else None
        }

    def _find_relevant_ranges(self, context: FileContext, key_terms: List[str]) -> List[Tuple[int, int]]:
        """Find line ranges relevant to key terms."""
        ranges = []
        lines = context.content.split('\n')

        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            if any(term in line_lower for term in key_terms):
                # Expand range to include context
                start = max(1, i - 2)
                end = min(len(lines), i + 2)
                ranges.append((start, end))

        # Merge overlapping ranges
        merged = []
        for start, end in sorted(ranges):
            if merged and merged[-1][1] >= start - 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        return merged

    def _parse_unified_diff(self, diff: str) -> Dict[str, Dict[str, Any]]:
        """Parse unified diff to extract changed files and lines."""
        file_changes = {}
        current_file = None
        modified_lines = []

        for line in diff.split('\n'):
            if line.startswith('--- '):
                current_file = line[4:].split('\t')[0]
            elif line.startswith('+++ '):
                current_file = line[4:].split('\t')[0]
            elif line.startswith('@@'):
                # Parse hunk header
                match = re.match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
                if match:
                    line_num = int(match.group(2))
                    modified_lines.append(line_num)

            if current_file and current_file != '/dev/null':
                if current_file not in file_changes:
                    file_changes[current_file] = {
                        'modified_lines': []
                    }
                file_changes[current_file]['modified_lines'].extend(modified_lines)
                modified_lines = []

        return file_changes

    def _resolve_import(self, from_file: Path, import_name: str) -> Optional[Path]:
        """Try to resolve an import to a file path."""
        # Simplified import resolution
        if from_file.suffix == '.py':
            # Python import
            parts = import_name.split('.')
            potential_paths = [
                self.project_root / f"{'/'.join(parts)}.py",
                self.project_root / f"{'/'.join(parts)}/__init__.py",
                from_file.parent / f"{parts[-1]}.py"
            ]
        else:
            # JavaScript/TypeScript import
            if import_name.startswith('.'):
                base = from_file.parent
                potential_paths = [
                    base / f"{import_name}.js",
                    base / f"{import_name}.ts",
                    base / f"{import_name}/index.js",
                    base / f"{import_name}/index.ts"
                ]
            else:
                # Node module
                return None

        for path in potential_paths:
            if path.exists():
                return path

        return None

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature from AST node."""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        return f"{node.name}({', '.join(args)})"

    def _find_configs(self) -> List[str]:
        """Find configuration files."""
        configs = []
        for pattern_list in self.config_patterns.values():
            for pattern in pattern_list:
                for path in self.project_root.glob(pattern):
                    if path.is_file():
                        configs.append(str(path.relative_to(self.project_root)))
        return configs

    def _find_guides(self) -> List[str]:
        """Find documentation and guide files."""
        guides = []
        for pattern in self.guide_patterns:
            for path in self.project_root.glob(pattern):
                if path.is_file():
                    guides.append(str(path.relative_to(self.project_root)))
        return guides

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed repository."""
        stats = {
            "total_files": len(self.file_index),
            "total_symbols": len(self.symbol_index),
            "total_imports": len(self.import_graph),
            "languages_detected": list(set(
                context.language for context in self.file_index.values()
            )),
            "indexed": bool(self.file_index)
        }

        # Add test file counts by checking file paths
        test_files = [f for f in self.file_index.keys() if self._is_test_file(Path(f))]
        stats["test_files"] = len(test_files)

        return stats