from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, Optional, List

class AgentAction(BaseModel):
    """Record of an agent's action and context"""
    timestamp: datetime = Field(description="When the action occurred, serves as the primary key")
    action_type: str = Field(description="Type of action (e.g., 'trade_decision', 'analysis', etc.)")
    action_details: Dict[str, Any] = Field(description="Details of the action taken")
    context: Dict[str, Any] = Field(description="Market/environment context when action occurred")
    reasoning: Optional[str] = Field(None, description="Agent's reasoning for this action")
    outcome: Optional[Dict[str, Any]] = Field(None, description="Result of the action, filled in later")

class PerformanceMetric(BaseModel):
    """Performance metric tracked over time"""
    metric_name: str = Field(description="Name of the performance metric, part of composite primary key")
    timestamp: datetime = Field(description="When the metric was recorded, part of composite primary key")
    value: float = Field(description="Value of the metric")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for this metric")

class ImprovementSuggestion(BaseModel):
    """Suggested improvement for agent performance"""
    id: Optional[int] = Field(None, description="Database ID for this suggestion")
    title: str = Field(description="Brief title for the suggestion")
    description: str = Field(description="Detailed description of the suggestion")
    reasoning: str = Field(description="Reasoning behind this suggestion")
    expected_impact: str = Field(description="Expected impact on performance")
    confidence: float = Field(description="Confidence level (0-1)")
    implementation_hints: List[str] = Field(description="Hints for implementing the suggestion")

class ImplementedSuggestion(BaseModel):
    """Record of a suggestion that was implemented"""
    id: Optional[int] = Field(None, description="Database ID for this implementation record")
    suggestion: ImprovementSuggestion = Field(description="The original suggestion")
    implementation_time: datetime = Field(description="When the suggestion was implemented")
    metrics_before: Dict[str, float] = Field(description="Metrics at time of implementation")
    metrics_after: Optional[Dict[str, float]] = Field(None, description="Metrics after implementation (if analyzed)")
    success_rating: Optional[float] = Field(None, description="User rating of success (0-1)")
    notes: Optional[str] = Field(None, description="User notes about implementation")

class SuggestionList(list):
    """A list container for ImprovementSuggestion objects"""
    def __init__(self, suggestions=None):
        super().__init__(suggestions or [])