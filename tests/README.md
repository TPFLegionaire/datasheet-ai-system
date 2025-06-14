# Datasheet AI Comparison System - Test Suite

This directory contains all automated tests for the Datasheet AI Comparison System. We use `pytest` as the test runner and `pytest-cov` for code coverage, ensuring our application is robust and reliable.

## 1. Running Tests

### Prerequisites

Before running tests, ensure you have all development dependencies installed. These include `pytest` for running the tests and `pytest-cov` for measuring code coverage. Your main project dependencies from `requirements.txt` must also be installed.

1.  **Navigate to the project root directory** (the one containing the `tests/` folder and `requirements.txt`).
2.  **Install test-specific dependencies**:
    ```bash
    pip install pytest pytest-cov flake8 bandit
    ```
3.  **Install project dependencies**:
    ```bash
    pip install -r ../requirements.txt 
    # If you are in the tests/ directory, use ../requirements.txt
    # If you are in the project root, use requirements.txt
    ```

### Running All Tests

To execute the entire test suite, run the following command from the **project root directory**:

```bash
pytest
```

Alternatively, if you are inside the `tests/` directory, you might need to ensure Python can find the project modules:

```bash
python -m pytest .
```
Running from the project root is generally recommended as `pytest` can better discover modules and `conftest.py`.

### Running Specific Test Files or Tests

You can run tests for a particular file:

```bash
pytest tests/test_pdf_extractor.py
```

To run a specific test function by its name (or part of its name) using the `-k` flag (keyword expression):

```bash
pytest -k "test_save_and_get_datasheet"
```

To run a specific test class or method within a file:

```bash
pytest tests/test_database.py::TestDatabaseManager::test_save_and_get_datasheet
```

### Verbose Output

For more detailed output from the test execution, use the `-v` flag:

```bash
pytest -v
```

This will show each test function name and its status (pass/fail).

## 2. Test Organization

The test suite is structured to mirror the project's main codebase, making it easy to locate tests for specific modules:

*   `tests/test_pdf_extractor.py`: Contains unit tests for the PDF parsing and data extraction logic found in `pdf_extractor.py`.
*   `tests/test_database.py`: Focuses on testing all database operations (CRUD, queries, backups) defined in `database.py`.
*   `tests/test_mistral_processor.py`: Tests the integration with the Mistral AI API, including prompt generation and response parsing from `mistral_processor.py`.
*   `tests/test_ai_integration.py`: Validates the hybrid extraction system in `ai_integration.py` that combines pattern-based and AI-assisted methods.
*   `tests/test_batch_processor.py`: Covers the functionality of `batch_processor.py` for handling multiple file uploads and processing.
*   `tests/test_auth.py`: Includes tests for user authentication, registration, session management, and role-based permissions from `auth.py`.
*   `tests/conftest.py`: This is a special `pytest` file used to define shared **fixtures** and configurations that are available to all test files in this directory.

## 3. Fixtures (`conftest.py`)

Fixtures are a powerful feature of `pytest` that provide a fixed baseline upon which tests can reliably and repeatedly execute. They are used for setting up preconditions for tests (like creating database connections, mock objects, or sample data) and for cleaning up resources after tests are done.

Our `tests/conftest.py` file centralizes many of these common setups:

*   **Mock Objects**: For external services like the Mistral AI API (`mock_mistral_client`, `mock_mistral_processor`) or internal components (`mock_pdf_extractor`, `mock_db_manager`). This allows testing modules in isolation.
*   **Sample Data**: Provides consistent data for tests, such as `sample_pdf_text_content`, `sample_mistral_extraction_response_success`, and various `DatasheetExtraction` objects representing different scenarios (e.g., `sample_pattern_extraction_result_strong`, `sample_ai_data_dict_good`).
*   **Instance Fixtures**: Create instances of our classes like `pdf_extractor_instance`, `in_memory_db_manager`, `auth_manager`, etc., often configured for testing (e.g., using an in-memory database).
*   **Utility Fixtures**: Helper functions for creating temporary files or directories needed during tests (e.g., `create_dummy_pdf`, `temp_files_factory`).

By using fixtures, we avoid duplicating setup code in each test and make our tests cleaner and more maintainable. When `pytest` runs, it automatically discovers and injects these fixtures into test functions that request them as arguments.

## 4. Code Coverage

We use `pytest-cov` to generate code coverage reports. This helps identify parts of the codebase that are not exercised by our automated tests, guiding us to improve test completeness.

### Generating a Terminal Report

To run tests and see a coverage report directly in your terminal, including a summary of missing lines:

```bash
pytest --cov=. --cov-report=term-missing
```

*   `--cov=.` tells `pytest-cov` to measure coverage for all Python files in the current directory (project root) and its subdirectories.
*   `--cov-report=term-missing` displays a summary table and lists the line numbers that are not covered by any test.

### Generating an HTML Report

For a more detailed and interactive coverage report, you can generate an HTML version:

```bash
pytest --cov=. --cov-report=html
```

This command will create an `htmlcov/` directory in your project root. Open `htmlcov/index.html` in your web browser to explore the coverage data. You can click on individual files to see exactly which lines are covered (green), not covered (red), or partially covered.

### XML Report for CI/CD

Our Continuous Integration (CI) pipeline, defined in `.github/workflows/python-app.yml`, is configured to generate an XML coverage report:

```bash
pytest tests/ --cov=. --cov-report=xml
```

This creates a `coverage.xml` file. This XML file can be uploaded as a build artifact or consumed by external code quality services like Codecov or SonarQube to track coverage over time and integrate it into pull request checks.

**Coverage Requirements**: While aiming for high test coverage (e.g., 80-90%+) is a good goal, remember that coverage is a guide, not a definitive measure of test quality. Focus on writing meaningful tests for critical and complex parts of your application. 100% coverage doesn't guarantee bug-free code if the tests themselves are not well-designed.

## 5. Tips for Writing Good Tests

To ensure our test suite remains effective and maintainable, we follow these best practices:

*   **Test One Thing at a Time**: Each test function should ideally verify a single piece of functionality, behavior, or a specific scenario. This makes tests easier to understand and debug.
*   **Independent Tests**: Tests should be independent of each other. The order in which they run should not affect their outcome, and one test failing should not cause others to fail or behave unexpectedly.
*   **Readable Names**: Use clear, descriptive names for test files (e.g., `test_user_authentication.py`), test classes (e.g., `TestLoginProcess`), and test functions (e.g., `test_login_with_invalid_password_should_fail`).
*   **Arrange, Act, Assert (AAA)**: Structure your tests clearly with these three phases:
    *   **Arrange**: Set up all necessary preconditions and inputs for the test (e.g., create objects, mock dependencies, prepare data).
    *   **Act**: Execute the specific piece of code or function call you are testing.
    *   **Assert**: Verify that the outcome of the "Act" phase is as expected. Use `assert` statements to check conditions.
*   **Use Fixtures**: Leverage `pytest` fixtures (defined in `conftest.py` or locally within test files) for reusable setup and teardown code. This keeps tests DRY (Don't Repeat Yourself).
*   **Mock Dependencies**: When unit testing a module, mock its external dependencies (like database connections, API calls, file system interactions) to isolate the unit under test and make tests faster and more predictable. The `unittest.mock` library (accessible via `pytest-mock` plugin) is excellent for this.
*   **Test Edge Cases and Error Conditions**: Don't just test the "happy path" (expected, normal behavior). Include tests for:
    *   Invalid or unexpected inputs.
    *   Empty inputs or collections.
    *   Boundary conditions (e.g., min/max values).
    *   How your code handles expected exceptions (use `pytest.raises`).
*   **Keep Tests Fast**: Unit tests, in particular, should run quickly to provide fast feedback during development. If a test is slow, it might be an integration test in disguise or might need refactoring with better mocking.
*   **Maintainable Tests**: Write tests that are easy to read, understand, and maintain. Avoid overly complex logic within tests. Clear tests are as important as clear production code.
*   **Refactor Tests**: Just like production code, tests should be refactored when necessary to improve clarity, remove duplication, and adapt to changes in the codebase.
