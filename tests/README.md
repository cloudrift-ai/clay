# Clay Integration Tests

This directory contains comprehensive integration tests for Clay that verify end-to-end functionality across different types of queries and use cases.

## Test Structure

The integration tests are organized into focused modules using pure pytest functions:

### Test Files

1. **Simple Queries** (`test_simple_queries.py`)
   - Basic math operations (2+2, multiplication, division)
   - Simple factual questions
   - Basic file operations

2. **Coding Tasks** (`test_coding_tasks.py`)
   - Function creation (factorial, string reversal, sorting)
   - Code explanation and analysis
   - Algorithm implementation
   - Code debugging and optimization

3. **Complex Project Creation** (`test_complex_projects.py`)
   - Multi-file project generation
   - Web server projects (Flask)
   - Calculator applications
   - Data analysis projects
   - REST API creation
   - Utility libraries

4. **Task Routing** (`test_task_routing.py`)
   - Multi-model system verification
   - Task type classification testing
   - Model selection for different task types
   - Orchestrator vs agent routing

5. **Error Handling** (`test_error_handling.py`)
   - Invalid file operations
   - Ambiguous queries
   - Edge cases (empty queries, special characters)
   - Multilingual query handling
   - Resource-intensive requests

### Test Helper

Tests use automatic fixtures for session management and cleanup:
- Automatic test directory creation in `_test/<test_name>/`
- Session creation utilities
- Response quality assertions
- Automatic cleanup after tests

## Running Tests

### Prerequisites

1. **API Keys**: At least one API key must be configured:
   ```bash
   clay config --set-api-key cloudrift YOUR_KEY
   # or
   clay config --set-api-key anthropic YOUR_KEY
   # or
   clay config --set-api-key openai YOUR_KEY
   ```

2. **Dependencies**: Install pytest:
   ```bash
   pip install pytest pytest-asyncio
   ```

### Test Execution

#### Run All Tests
```bash
# Run all integration tests
pytest tests/integration/ -v

# Run tests with coverage
pytest tests/integration/ --cov=clay -v
```

#### Run Specific Test Modules
```bash
# Simple queries only
pytest tests/integration/test_simple_queries.py -v

# Coding tasks only
pytest tests/integration/test_coding_tasks.py -v

# Complex project creation
pytest tests/integration/test_complex_projects.py -v

# Task routing verification
pytest tests/integration/test_task_routing.py -v

# Error handling tests
pytest tests/integration/test_error_handling.py -v
```

#### Run Specific Test Functions
```bash
# Run specific test function
pytest tests/integration/test_simple_queries.py::test_basic_math -v

# Run tests matching pattern
pytest tests/integration/ -k "math" -v
```

### Test Configuration

Tests use pytest markers for organization:
- `@pytest.mark.asyncio`: Asynchronous test functions

## Expected Behavior

### Simple Queries
- **Input**: "what is 2+2?"
- **Expected**: Direct answer "4"
- **Model**: Fast reasoning model (DeepSeek-V3)
- **Agent**: Direct agent execution

### Coding Tasks
- **Input**: "write a function to calculate factorial"
- **Expected**: Code generation with file creation
- **Model**: Coding-optimized model
- **Agent**: Coding agent with tool execution

### Complex Projects
- **Input**: "Create a Flask web server with templates"
- **Expected**: Multiple files created (app.py, requirements.txt, templates)
- **Model**: Complex reasoning or orchestrator
- **Behavior**: Multi-step execution plan

## Test Output Examples

### Successful Simple Query
```
🤖 coding_agent Agent: what is 2+2?
→ Using simple reasoning model: cloudrift:DeepSeek-V3
4
```

### Successful Coding Task
```
🤖 coding_agent Agent: write a function to calculate factorial
→ Using coding model: cloudrift:DeepSeek-V3
➤ Executing write: factorial.py
  → Created new file with 15 lines
```

### Complex Project
```
🤖 coding_agent Agent: Create a Flask web server
→ Using complex reasoning model: cloudrift:DeepSeek-V3
➤ Executing write: app.py
  → Created new file with 25 lines
➤ Executing write: requirements.txt
  → Created new file with 3 lines
```

## Troubleshooting

### Common Issues

1. **No API Keys**
   ```
   ❌ No API keys found. Integration tests require at least one API key.
   ```
   **Solution**: Configure API keys using `clay config --set-api-key`

2. **Import Errors**
   ```
   ModuleNotFoundError: No module named 'clay'
   ```
   **Solution**: Run tests from project root directory

3. **Timeout Issues**
   ```
   AssertionError: Response too short
   ```
   **Solution**: Some models may be slow; increase timeout or skip slow tests

### Test Development

When adding new tests:

1. Use `run_clay_command(query)` helper function from `test_helpers.py`
2. Tests automatically get isolated directories in `_test/<test_name>/`
3. Use realistic expectations (models may not always create files)
4. No manual setup or cleanup needed - handled automatically by fixtures
5. Tests use Clay's default configuration and CLI interface

### Performance Considerations

- Simple tests should complete in <10 seconds
- Coding tests may take 10-30 seconds
- Complex project tests may take 30+ seconds

## Integration with CI/CD

For automated testing environments:

```bash
# Run test suite
pytest tests/integration/ -v --tb=short

# Generate test report
pytest tests/integration/ --html=test_report.html

# Run tests in parallel
pytest tests/integration/ -n 4 -v
```