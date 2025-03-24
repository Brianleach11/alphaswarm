# Directory Contents

```
evolution/
├── __init__.py                      # Module exports
├── models.py                        # Pydantic data models
├── evolution_agent.py               # Core agent implementation
├── README.md                        # This documentation file
├── sqlite_helpers.py                # Relevant methods to interface with sqlite
├── suggestion_command_handler.py    # CLI for suggestion options
└── prompts/
    ├── system_prompt.md     # LLM system instructions
    └── user_prompt.md       # LLM user prompt template
    └── prompt_templates.py  # Planning steps for CodeAgent

```

# Technical Implementation

## evolution_agent.py

- The core implementation of the Evolution Agent

### Key Implementation Features:

**Smolagents - CoderAgent:**
- Overwrites the system prompt for a more accurate analysis.
- Custom database query tool for CodeAgent utilization.
- Extensive planning prompts and re-planning every 2 steps.

**Efficient Storage:**
- Utilizes sqlite3 package to persist data after closing the agent. 
- When restarting the AlphaSwarmAgent / EvolutionAgent pair, it will load previous data.
- Automatic pruning of old records to manage memory usage<br/>

**Data Recording Interface:**

- _record_action_: Creates and stores a new action record
- _record_outcome_: Updates an existing action with its outcome
- _record_metric_: Records a performance metric at a point in time<br/>

**Analysis Timing Logic:**

- Automatically determines when analysis should occur
- Respects minimum data requirements and time intervals
- Allows forced analysis when needed<br/>

**AlphaSwarmToolBase Integration:**

- Implements the _forward()_ method required by the tool interface
- Accepts a _force_analysis_ parameter to allow on-demand analysis
- Returns structured _ImprovementSuggestion_ List[]<br/>


## models.py
**AgentAction**: Tracks individual agent actions and their outcomes

- _timestamp_ serves as a unique identifier for actions
- _outcome_ is initially None and updated later when results are known<br/>

**PerformanceMetric**: Captures calculated performance statistics

- Organized by _metric_name_ to track different metrics over time
- Includes timestamps for trend analysis<br/>

**ImprovementSuggestion**: Structured format for suggested improvements

- Includes confidence level and expected impact for prioritization
- References specific historical actions as supporting evidence<br/>

**ImplementedSuggestion**: Tracks suggestions that have been implemented

- Captures _metrics_before_ and _metrics_after_ for impact analysis
- Includes user feedback via _success_rating_ and _notes_
- Creates a continuous improvement feedback loop<br/>

## suggestion_command_helper.py

**Suggestion Management Interface:**

- Command-based interaction (!suggestion commands)
- Tracks which suggestions were implemented and their impact
- Allows users to rate suggestions and provide feedback
- Uses this feedback to improve future suggestions<br/>

## system_prommpt.md

- The system prompt sets the role for the LLM
- Provides an example of an agentic process
- Defines strict rules to abide by

## user_prompt.md

- The user prompt template that kicks off the agentic process, with brief hints.

# Usage Guide

To use the Evolution Agent in an AlphaSwarm implementation:

1. **Initialize the Agent:**

```python
from alphaswarm.tools.evolution import EvolutionAgent

evolution_agent = EvolutionAgent(
    model_id="anthropic/claude-3-5-sonnet-20241022",
    client_id="[AlphaSwarmAgent.client_id]"
    analysis_interval_hours=24,          # How often analysis runs
    min_actions_required=10              # Minimum actions before analysis
)
```

2. **Add to AlphaSwarmAgent tools:**

```python
from alphaswarm.agent.agent import AlphaSwarmAgent

agent = AlphaSwarmAgent(
    tools=[evolution_agent, ...other_tools],
    model_id="anthropic/claude-3-5-sonnet-20241022"
)
```

3. **Record Actions and Outcomes:**

```python
# When a trading decision is made, purely example.
timestamp = evolution_agent.record_action(
    action_type="trade_decision",
    action_details={"token": "WETH", "action": "buy", "amount": 0.5},
    context={"market_trend": "bullish", "volume": "increasing"},
    reasoning="Strong price momentum with increasing volume"
)

# Later, when the outcome is known, purely example.
evolution_agent.record_outcome(
    action_timestamp=timestamp,
    outcome={"pnl_percent": 3.5, "hold_time_hours": 24, "slippage_bps": 8}
)
```

4. **Record Performance Metrics:**

```python
evolution_agent.record_metric(
    metric_name="win_rate_7d",
    value=0.65,  # 65% win rate
    context={"trades_counted": 20}
)
```

5. **Add Suggestion Command Processing:**

```
class MyClientAgent:
    def __init__(self, model_id="anthropic/claude-3-5-sonnet-20241022"):
        # Initialize tools including evolution agent
        self.evolution_agent = EvolutionAgent(
            client_id="my_client",
            model_id=model_id
        )
        
        # Create the AlphaSwarmAgent with tools
        self.agent = AlphaSwarmAgent(
            tools=[self.evolution_agent, ...other_tools],
            model_id=model_id
        )
    
    async def process_message(self, current_message: str) -> Optional[str]:
        try:
            # Check if this is a suggestion command for the evolution agent
            cmd_response = self.evolution_agent.process_command(current_message)
            if cmd_response is not None:
                return cmd_response

            # If not a command, continue with normal processing using the base agent
            return await self.agent.process_message(current_message)

        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"
```

6. **Request Improvement Suggestions:**

```python
# User asks for suggestions
user_message = "Can you suggest improvements to my trading strategy?"

# The LLM will invoke evolution_agent.forward(force_analysis=True)
# which returns a list of ImprovementSuggestion objects
response = agent.process_message(user_message)
```

7. **Implement and Rate Suggestions:**

After receiving suggestions, users can implement and rate them using the command interface:

```python
# Mark a suggestion as implemented
user_message = "!suggestion implement 2 I've adjusted the stop-loss parameters as suggested"

# Later, rate how well it worked
user_message = "!suggestion rate 1 0.85 Performed well in volatile markets"

# Check status of all implemented suggestions
user_message = "!suggestion status"
```

# Evolution Agent Command Interface Guide

The command interface allows users to interact with suggestions through the chat:

```
!suggestion list              - List recent suggestions
!suggestion implement 2 notes - Mark suggestion #2 as implemented with notes
!suggestion status            - View status of implemented suggestions
!suggestion rate 1 0.8 notes  - Rate suggestion #1 with score 0.8/1.0
!suggestion prune             - Prune all sqlite data (irreversible)
!suggestion help              - Show available commands
```

## Suggestion Tracking Workflow

1. The agent analyzes performance and generates suggestions
2. Users implement suggestions they find valuable
3. They mark them as implemented using `!suggestion implement`
4. Later, they rate effectiveness using `!suggestion rate`
5. The system captures before/after metrics automatically
6. This feedback informs future suggestions, creating a continuous improvement loop

# Implementation Notes

- The Evolution Agent maintains its own history independently of the AlphaSwarmAgent
- It requires explicit recording of actions and outcomes
- Automatic pruning prevents unbounded memory growth
- Suggestions are structured for consistent parsing and presentation
- The command system allows natural interaction through the chat interface
- Suggestion tracking creates a feedback loop for continuous improvement
