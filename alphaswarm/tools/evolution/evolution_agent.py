from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3
import pandas as pd

from alphaswarm import BASE_PATH
from alphaswarm.core.tool import AlphaSwarmToolBase
from alphaswarm.tools.evolution.models import AgentAction, ImprovementSuggestion, ImplementedSuggestion, PerformanceMetric

from smolagents import CODE_SYSTEM_PROMPT, CodeAgent, LiteLLMModel, tool, PromptTemplates, PlanningPromptTemplate, FinalAnswerPromptTemplate
from alphaswarm.tools.evolution.suggestion_command_handler import SuggestionCommandHandler

from alphaswarm.tools.evolution.sqlite_helpers import (
    create_agent_tables,
    get_action,
    store_action,
    store_metric,
    prune_old_data,
    load_last_analysis_time,
    load_suggestions,
    load_implemented_suggestions,
    store_last_analysis_time,
    store_suggestion,
    store_implemented_suggestion,
    count_actions_with_outcomes,
    get_latest_metrics,
    prune_all_data,
    update_implemented_suggestion
)

from alphaswarm.tools.evolution.prompts.prompt_templates import (
    PLANNING_INITIAL_FACTS,
    PLANNING_INITIAL_PLAN,
    PLANNING_UPDATE_FACTS_PRE_MESSAGES,
    PLANNING_UPDATE_FACTS_POST_MESSAGES,
    PLANNING_UPDATE_PLAN_PRE_MESSAGES,
    PLANNING_UPDATE_PLAN_POST_MESSAGES,
    FINAL_ANSWER_PRE_MESSAGES,
    FINAL_ANSWER_POST_MESSAGES,
)
TOOLS_PATH = Path(BASE_PATH) / "alphaswarm" / "tools"

class EvolutionAgent(AlphaSwarmToolBase):
    def __init__(
        self,
        client_id: str,
        model_id: str = "anthropic/claude-3-5-sonnet-20241022",
        analysis_interval_hours: int = 24,
        min_actions_required: int = 10,
        max_history_days: int = 30,
        *args: Any,
        **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.model_id = model_id
        self.analysis_interval_hours = analysis_interval_hours
        self.min_actions_required = min_actions_required
        self.max_history_days = max_history_days
        self.client_id = client_id
        self.last_analysis_time: Optional[datetime] = None
        self.last_suggestions: List[ImprovementSuggestion] = []
        self.implemented_suggestions: List[ImplementedSuggestion] = []
        self.suggestion_command_handler = SuggestionCommandHandler(self)

        self.db_name = f"{self.client_id.lower().replace(' ', '_')}.db"
        create_agent_tables(self.db_name)
        self.import_history(self.db_name)

        self.prompts_path = TOOLS_PATH / "evolution" / "prompts"
        self._setup_agent(self.prompts_path)

    def _setup_agent(self, prompts_path: Path) -> None:
        model = LiteLLMModel(model_id=self.model_id)

        @tool
        def query_database(sql: str) -> str:
            conn = sqlite3.connect(self.db_name)
            try:
                df = pd.read_sql_query(sql, conn)
                return df.to_string()
            except Exception as e:
                return f"Error: {e}"
            finally:
                conn.close()

        prompt_templates = PromptTemplates(
            system_prompt=open(prompts_path / "system_prompt.md").read() | CODE_SYSTEM_PROMPT,
            planning=PlanningPromptTemplate(
                initial_facts=PLANNING_INITIAL_FACTS,
                initial_plan=PLANNING_INITIAL_PLAN,
                update_facts_pre_messages=PLANNING_UPDATE_FACTS_PRE_MESSAGES,
                update_facts_post_messages=PLANNING_UPDATE_FACTS_POST_MESSAGES,
                update_plan_pre_messages=PLANNING_UPDATE_PLAN_PRE_MESSAGES,
                update_plan_post_messages=PLANNING_UPDATE_PLAN_POST_MESSAGES,
            ),
            final_answer=FinalAnswerPromptTemplate(
                pre_messages=FINAL_ANSWER_PRE_MESSAGES,
                post_messages=FINAL_ANSWER_POST_MESSAGES,
            ),
        )

        self.evolution_agent = CodeAgent(
            tools=[query_database],
            model=model,
            prompt_templates=prompt_templates,
            additional_authorized_tools=["datetime", "numpy", "pandas", "json", "collections"],
            planning_interval=2,
            executor_type="local",
        )
        
    def record_action(
        self,
        action_type: str,
        action_details: Dict[str, Any],
        context: Dict[str, Any] = None,
        reasoning: str = None,
    ) -> datetime:
        timestamp = datetime.now()
        action = AgentAction(
            timestamp=timestamp,
            action_type=action_type,
            action_details=action_details,
            context=context or {},
            reasoning=reasoning,
        )
        store_action(self.db_name, action)
        prune_old_data(self.db_name, self.max_history_days)
        return timestamp
       
    def record_outcome(
        self,
        action_timestamp: datetime,
        outcome: Dict[str, Any]
    ) -> bool:
        try:
            current_action = get_action(self.db_name, action_timestamp)
            action = AgentAction(
                timestamp=action_timestamp,
                action_type=current_action.action_type,
                action_details=current_action.action_details,
                context=current_action.context,
                outcome=outcome
            )
            store_action(self.db_name, action)
        except Exception as e:
            print(f"Error storing action: {e}")
            return False
            
        return True
    
    def record_metric(
        self,
        metric_name: str,
        value: float,
        context: Dict[str, Any] = None,
    ) -> None:
        timestamp = datetime.now()
        metric = PerformanceMetric(
            metric_name=metric_name,
            timestamp=timestamp,
            value=value,
            context=context or {},
        )
    
        store_metric(self.db_name, metric)
    
        prune_old_data(self.db_name, self.max_history_days)

    def process_command(self, message: str) -> Optional[str]:
        return self.suggestion_command_handler.process_command(message)

    def forward(self, force_analysis: bool = False) -> List[ImprovementSuggestion]:      
        time_condition = (
            self.last_analysis_time is None or
            (datetime.now() - self.last_analysis_time) >=
            timedelta(hours=self.analysis_interval_hours)
        )
        valid_actions = count_actions_with_outcomes(self.db_name)
        data_condition = (
            valid_actions >= self.min_actions_required
        )

        if not (time_condition or (force_analysis and data_condition)):
            return []
        
        self.last_analysis_time = datetime.now()
    
        store_last_analysis_time(self.db_name, self.last_analysis_time)
        
        user_prompt = open(self.prompts_path / "user_prompt.md").read()
        
        response = self.evolution_agent.run(user_prompt)

        self.last_suggestions = response

        for suggestion in response:
            suggestion_id = store_suggestion(self.db_name, suggestion)
            suggestion.id = suggestion_id
            
        return response
    
    def implement_suggestion(self, 
                            suggestion_index: int, 
                            notes: Optional[str] = None) -> Optional[ImplementedSuggestion]:
        if not self.last_suggestions or suggestion_index < 0 or suggestion_index >= len(self.last_suggestions):
            return None
            
        current_metrics = get_latest_metrics(self.db_name)
        suggestion = self.last_suggestions[suggestion_index]
                
        implemented = ImplementedSuggestion(
            suggestion=suggestion,
            implementation_time=datetime.now(),
            metrics_before=current_metrics,
            notes=notes
        )
        
        if suggestion.id is None:
            suggestion.id = store_suggestion(self.db_name, suggestion)
        
        implementation_id = store_implemented_suggestion(self.db_name, implemented, suggestion.id)
        implemented.id = implementation_id
        
        self.implemented_suggestions.append(implemented)
        
        return implemented
    
    def analyze_suggestion_impact(self, 
                                implemented_index: int, 
                                success_rating: Optional[float] = None) -> bool:
        if not self.implemented_suggestions or implemented_index < 0 or implemented_index >= len(self.implemented_suggestions):
            return False
            
        implemented = self.implemented_suggestions[implemented_index]
        
        current_metrics = get_latest_metrics(self.db_name)
                
        implemented.metrics_after = current_metrics
        
        if success_rating is not None:
            implemented.success_rating = max(0.0, min(1.0, success_rating))

        if implemented.id is None:
            print(f"Warning: Implemented suggestion has no ID. Skipping update.")
            return False

        return update_implemented_suggestion(self.db_name, implemented)
    
    def import_history(self, db_name: str) -> bool:
        try:
            last_analysis = load_last_analysis_time(db_name)
            if last_analysis:
                self.last_analysis_time = last_analysis
                
            suggestions = load_suggestions(db_name)
            if suggestions:
                self.last_suggestions = suggestions
                
            implemented_suggestions = load_implemented_suggestions(db_name)
            if implemented_suggestions:
                self.implemented_suggestions = implemented_suggestions
            
            return True
        except Exception as e:
            print(f"Error importing data from SQLite: {e}")
            return False