import pytest
from unittest.mock import patch
from datetime import datetime
import sqlite3
import os
import tempfile

from alphaswarm.tools.evolution.evolution_agent import EvolutionAgent
from alphaswarm.tools.evolution.models import (
    ImprovementSuggestion,
    ImplementedSuggestion,
)

# Create a connection wrapper to prevent closure
class ConnectionWrapper:
    def __init__(self, connection):
        self.connection = connection
        
    def cursor(self):
        return self.connection.cursor()
        
    def execute(self, *args, **kwargs):
        return self.connection.execute(*args, **kwargs)
        
    def commit(self):
        return self.connection.commit()
        
    def rollback(self):
        return self.connection.rollback()
        
    def close(self):
        # Intentionally do nothing to prevent connection closing
        pass
    
    def __getattr__(self, name):
        # Forward any other attribute access to the underlying connection
        return getattr(self.connection, name)


@pytest.fixture
def temp_db_file():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def mock_db_conn(temp_db_file):
    """Set up a real SQLite connection with the schema."""
    real_conn = sqlite3.connect(temp_db_file)
    
    # Create tables with names matching those in sqlite_helpers.py
    real_conn.execute("""
        CREATE TABLE actions (
            timestamp TEXT PRIMARY KEY,
            action_type TEXT,
            action_details TEXT,
            context TEXT,
            reasoning TEXT,
            outcome TEXT
        )
    """)
    
    real_conn.execute("""
        CREATE TABLE metrics (
            metric_name TEXT,
            timestamp TEXT,
            value REAL,
            context TEXT,
            PRIMARY KEY (metric_name, timestamp)
        )
    """)
    
    real_conn.execute("""
        CREATE TABLE suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            reasoning TEXT,
            expected_impact TEXT,
            confidence REAL,
            implementation_hints TEXT
        )
    """)
    
    real_conn.execute("""
        CREATE TABLE implemented_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suggestion_id INTEGER,
            implementation_time TEXT,
            metrics_before TEXT,
            metrics_after TEXT,
            success_rating REAL,
            notes TEXT,
            FOREIGN KEY (suggestion_id) REFERENCES suggestions (id)
        )
    """)
    
    real_conn.execute("""
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Wrap the connection to prevent closing
    conn = ConnectionWrapper(real_conn)
    yield conn
    
    # Now actually close the connection
    real_conn.close()


@pytest.fixture
def evolution_agent(monkeypatch, temp_db_file, mock_db_conn):
    """Create an EvolutionAgent instance for testing."""
    # Mock all sqlite3 database connections to return our mock connection
    with patch('alphaswarm.tools.evolution.evolution_agent.sqlite3.connect') as mock_connect, \
         patch('alphaswarm.tools.evolution.sqlite_helpers.sqlite3.connect') as mock_helpers_connect:
        
        mock_connect.return_value = mock_db_conn
        mock_helpers_connect.return_value = mock_db_conn
        
        # Create the agent
        agent = EvolutionAgent(
            client_id="test_client",
            model_id="test_model",
            analysis_interval_hours=24,
            min_actions_required=3,
            max_history_days=30
        )
        
        yield agent


class TestEvolutionAgent:
    """Tests for the EvolutionAgent class."""
    
    def test_initialization(self, evolution_agent):
        """Test that the agent initializes correctly."""
        assert evolution_agent.client_id == "test_client"
        assert evolution_agent.model_id == "test_model"
        assert evolution_agent.analysis_interval_hours == 24
        assert evolution_agent.min_actions_required == 3
        assert evolution_agent.max_history_days == 30
    
    def test_record_action(self, evolution_agent, mock_db_conn):
        """Test recording an agent action."""
        timestamp = evolution_agent.record_action(
            action_type="test_action",
            action_details={"param": "value"},
            context={"market": "up"},
            reasoning="Test reasoning"
        )
        
        # Verify the action was stored in the database
        cursor = mock_db_conn.cursor()
        cursor.execute("SELECT * FROM actions WHERE action_type = ?", ("test_action",))
        row = cursor.fetchone()
        
        assert row is not None
        assert row[1] == "test_action"  # action_type
        assert "param" in row[2]  # action_details (JSON string)
        assert "market" in row[3]  # context (JSON string)
        assert row[4] == "Test reasoning"  # reasoning
        assert row[5] is None  # outcome (not set yet)
    
    def test_record_outcome(self, evolution_agent, mock_db_conn):
        """Test recording an outcome for an existing action."""
        # First record an action
        timestamp = evolution_agent.record_action(
            action_type="test_action",
            action_details={"param": "value"}
        )
        
        # Then record its outcome
        result = evolution_agent.record_outcome(
            action_timestamp=timestamp,
            outcome={"result": "success"}
        )
        
        assert result is True
        
        # Verify the outcome was stored
        cursor = mock_db_conn.cursor()
        cursor.execute("SELECT outcome FROM actions WHERE timestamp = ?", (timestamp.isoformat(),))
        row = cursor.fetchone()
        
        assert row is not None
        assert "result" in row[0]  # outcome (JSON string)
    
    def test_record_metric(self, evolution_agent, mock_db_conn):
        """Test recording a performance metric."""
        evolution_agent.record_metric(
            metric_name="test_metric",
            value=0.85,
            context={"source": "test"}
        )
        
        # Verify the metric was stored
        cursor = mock_db_conn.cursor()
        cursor.execute("SELECT * FROM metrics WHERE metric_name = ?", ("test_metric",))
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] == "test_metric"  # metric_name
        assert float(row[2]) == 0.85  # value
        assert "source" in row[3]  # context (JSON string)
    
    def test_forward_with_force_analysis(self, evolution_agent):
        """Test the forward method with force_analysis=True."""
        # Set up mock suggestions
        mock_suggestions = [
            ImprovementSuggestion(
                title="Increase stop-loss threshold by 2%",
                description="Adjust the current stop-loss settings to prevent early exits",
                reasoning="Analysis shows current stop-loss is triggering too early",
                expected_impact="5% improvement in win rate",
                confidence=0.85,
                implementation_hints=[
                    "Modify threshold in config.py",
                    "Test with historical data first"
                ]
            ),
            ImprovementSuggestion(
                title="Add volume analysis to entry criteria",
                description="Include volume metrics in trade entry decision",
                reasoning="Current entries occur in low liquidity conditions",
                expected_impact="Reduced slippage by 15%",
                confidence=0.75,
                implementation_hints=[
                    "Calculate 24h volume average",
                    "Add minimum volume threshold"
                ]
            )
        ]
        
        # Replace the run method with a mock that returns our suggestions directly
        with patch.object(evolution_agent.evolution_agent, 'run', return_value=mock_suggestions):
            # Call the forward method with force_analysis=True
            suggestions = evolution_agent.forward(force_analysis=True)
            
            # Check that suggestions match what we expect
            assert len(suggestions) == 2
            assert suggestions[0].title == "Increase stop-loss threshold by 2%"
            assert suggestions[0].confidence == 0.85
            assert suggestions[1].title == "Add volume analysis to entry criteria"
            assert suggestions[1].confidence == 0.75
    
    def test_implement_suggestion(self, evolution_agent, mock_db_conn):
        """Test implementing a suggestion."""
        # First, store a suggestion in the database
        cursor = mock_db_conn.cursor()
        cursor.execute(
            "INSERT INTO suggestions (title, description, reasoning, expected_impact, confidence, implementation_hints) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Test Suggestion", 
                "Description", 
                "Reasoning", 
                "Expected Impact", 
                0.9, 
                '["Hint 1", "Hint 2"]'
            )
        )
        mock_db_conn.commit()
        
        # Set up suggestion to be found
        suggestion = ImprovementSuggestion(
            id=1,
            title="Test Suggestion",
            description="Description",
            reasoning="Reasoning",
            expected_impact="Expected Impact",
            confidence=0.9,
            implementation_hints=["Hint 1", "Hint 2"]
        )
        evolution_agent.last_suggestions = [suggestion]
        
        # Record a metric to have data for metrics_before
        evolution_agent.record_metric("test_metric", 0.5)
        
        # Implement the suggestion (index 0 would be the first suggestion)
        implemented = evolution_agent.implement_suggestion(0, "Implementation notes")
        
        assert implemented is not None
        assert implemented.suggestion.title == "Test Suggestion"
        assert implemented.notes == "Implementation notes"
        
    def test_analyze_suggestion_impact(self, evolution_agent, mock_db_conn):
        """Test analyzing the impact of an implemented suggestion."""
        # First, store a suggestion and implemented suggestion
        cursor = mock_db_conn.cursor()
        cursor.execute(
            "INSERT INTO suggestions (title, description, reasoning, expected_impact, confidence, implementation_hints) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Test Suggestion", 
                "Description", 
                "Reasoning", 
                "Expected Impact", 
                0.9, 
                '["Hint 1", "Hint 2"]'
            )
        )
        suggestion_id = cursor.lastrowid
        
        cursor.execute(
            "INSERT INTO implemented_suggestions (suggestion_id, implementation_time, metrics_before, metrics_after, success_rating, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                suggestion_id,
                datetime.now().isoformat(),
                '{"test_metric": 0.5}',
                None,
                None,
                "Implementation notes"
            )
        )
        implementation_id = cursor.lastrowid
        mock_db_conn.commit()
        
        # Set up the implemented suggestion in memory
        suggestion = ImprovementSuggestion(
            id=suggestion_id,
            title="Test Suggestion",
            description="Description",
            reasoning="Reasoning",
            expected_impact="Expected Impact",
            confidence=0.9,
            implementation_hints=["Hint 1", "Hint 2"]
        )
        
        implemented = ImplementedSuggestion(
            id=implementation_id,
            suggestion=suggestion,
            implementation_time=datetime.now(),
            metrics_before={"test_metric": 0.5},
            notes="Implementation notes"
        )
        
        evolution_agent.implemented_suggestions = [implemented]
        
        # Record a new metric to have data for metrics_after
        evolution_agent.record_metric("test_metric", 0.8)
        
        # Analyze the impact and rate the suggestion
        result = evolution_agent.analyze_suggestion_impact(0, 0.85)
        
        assert result is True
    
    @patch('alphaswarm.tools.evolution.suggestion_command_handler.SuggestionCommandHandler.process_command')
    def test_process_command(self, mock_process_command, evolution_agent):
        """Test the process_command method."""
        mock_process_command.return_value = "Command processed successfully"
        
        result = evolution_agent.process_command("!suggestion list")
        
        assert result == "Command processed successfully"
        mock_process_command.assert_called_once_with("!suggestion list") 