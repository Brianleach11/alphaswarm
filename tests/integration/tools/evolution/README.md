# Evolution Agent Tests

This directory contains integration tests for the Evolution Agent tool.

## Test Overview

The tests in this directory verify that:

1. The Evolution Agent correctly records and retrieves actions, outcomes, and metrics
2. The suggestion command interface works properly
3. The Evolution Agent integrates correctly with the AlphaSwarmAgent
4. Data pruning functionality works as expected

## Running the Tests

To run all the Evolution Agent integration tests:

```bash
# Run from the project root directory
pytest tests/integration/tools/evolution/
```

To run a specific test:

```bash
# Run from the project root directory
pytest tests/integration/tools/evolution/test_evolution_integration.py::TestEvolutionIntegration::test_alphaswarm_agent_integration
```

## Unit Tests

Unit tests for the Evolution Agent are located in `tests/unit/tools/test_evolution_agent.py`. These tests focus on testing individual methods and functionality in isolation.

To run the unit tests:

```bash
# Run from the project root directory
pytest tests/unit/tools/test_evolution_agent.py
```

## Test Coverage

To generate test coverage for the Evolution Agent:

```bash
# Run from the project root directory
pytest tests/unit/tools/test_evolution_agent.py tests/integration/tools/evolution/ --cov=alphaswarm.tools.evolution --cov-report=term
```
