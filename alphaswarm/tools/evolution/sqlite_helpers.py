import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models import AgentAction, PerformanceMetric, ImprovementSuggestion, ImplementedSuggestion

def create_agent_tables(db_name: str) -> bool:
    conn = create_connection(db_name)
    create_table(conn, "actions", [
        "timestamp TEXT PRIMARY KEY",
        "action_type TEXT",
        "action_details TEXT",
        "context TEXT",
        "reasoning TEXT",
        "outcome TEXT"
    ])
    
    create_table(conn, "metrics", [
        "metric_name TEXT",
        "timestamp TEXT",
        "value REAL",
        "context TEXT",
        "PRIMARY KEY (metric_name, timestamp)"
    ])
    
    create_table(conn, "suggestions", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "title TEXT",
        "description TEXT",
        "reasoning TEXT",
        "expected_impact TEXT",
        "confidence REAL",
        "implementation_hints TEXT"
    ])
    
    create_table(conn, "implemented_suggestions", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "suggestion_id INTEGER",
        "implementation_time TEXT",
        "metrics_before TEXT",
        "metrics_after TEXT",
        "success_rating REAL",
        "notes TEXT",
        "FOREIGN KEY (suggestion_id) REFERENCES suggestions(id)"
    ])
    
    create_table(conn, "metadata", [
        "key TEXT PRIMARY KEY",
        "value TEXT"
    ])
    
    conn.close()
    return True

def count_actions_with_outcomes(db_name: str) -> int:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM actions WHERE outcome IS NOT NULL")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_latest_metrics(db_name: str) -> Dict[str, float]:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT metric_name, AVG(value) as value FROM metrics GROUP BY metric_name ORDER BY timestamp DESC LIMIT 1")
    rows = cursor.fetchall()
    return {row[0]: row[1] for row in rows}

def get_action(db_name: str, timestamp: datetime) -> AgentAction:
    from models import AgentAction
    conn = create_connection(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM actions WHERE timestamp = ?", (timestamp.isoformat(),))
    row = cursor.fetchone()
    if row:
        return AgentAction(
            timestamp=datetime.fromisoformat(row[0]),
            action_type=row[1],
            action_details=json.loads(row[2]),
            context=json.loads(row[3]),
            reasoning=row[4],
            outcome=json.loads(row[5]) if row[5] else None
        )
    return None

def store_action(db_name: str, action: AgentAction):
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR REPLACE INTO actions VALUES (?, ?, ?, ?, ?, ?)",
        (
            action.timestamp.isoformat(),
            action.action_type,
            json.dumps(action.action_details),
            json.dumps(action.context),
            action.reasoning,
            json.dumps(action.outcome) if action.outcome else None
        )
    )
    
    conn.commit()
    conn.close()

def store_metric(db_name: str, metric: PerformanceMetric):
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR REPLACE INTO metrics VALUES (?, ?, ?, ?)",
        (
            metric.metric_name,
            metric.timestamp.isoformat(),
            metric.value,
            json.dumps(metric.context) if metric.context else None
        )
    )
    
    conn.commit()
    conn.close()

def store_last_analysis_time(db_name: str, timestamp: Optional[datetime]):
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    value = timestamp.isoformat() if timestamp else None
    cursor.execute(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        ("last_analysis_time", value)
    )
    
    conn.commit()
    conn.close()

def store_suggestion(db_name: str, suggestion: ImprovementSuggestion) -> int:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    if suggestion.id is not None:
        cursor.execute("SELECT id FROM suggestions WHERE id = ?", (suggestion.id,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE suggestions SET title = ?, description = ?, reasoning = ?, expected_impact = ?, confidence = ?, implementation_hints = ? WHERE id = ?",
                (
                    suggestion.title,
                    suggestion.description,
                    suggestion.reasoning,
                    suggestion.expected_impact,
                    suggestion.confidence,
                    json.dumps(suggestion.implementation_hints),
                    suggestion.id
                )
            )
            conn.commit()
            conn.close()
            return suggestion.id
        
    cursor.execute(
        "INSERT INTO suggestions VALUES (NULL, ?, ?, ?, ?, ?, ?)",
        (
            suggestion.title,
            suggestion.description,
            suggestion.reasoning,
            suggestion.expected_impact,
            suggestion.confidence,
            json.dumps(suggestion.implementation_hints)
        )
    )
    
    suggestion_id = cursor.lastrowid
    suggestion.id = suggestion_id
    conn.commit()
    conn.close()
    
    return suggestion_id

def store_implemented_suggestion(db_name: str, impl_suggestion: ImplementedSuggestion, suggestion_id: int) -> int:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO implemented_suggestions VALUES (NULL, ?, ?, ?, ?, ?, ?)",
        (
            suggestion_id,
            impl_suggestion.implementation_time.isoformat(),
            json.dumps(impl_suggestion.metrics_before),
            json.dumps(impl_suggestion.metrics_after) if impl_suggestion.metrics_after else None,
            impl_suggestion.success_rating,
            impl_suggestion.notes
        )
    )
    
    implementation_id = cursor.lastrowid
    impl_suggestion.id = implementation_id
    
    conn.commit()
    conn.close()
    
    return implementation_id

def update_implemented_suggestion(db_name: str, impl_suggestion: ImplementedSuggestion) -> bool:
    if impl_suggestion.id is None:
        print(f"Warning: Cannot update implementation without an ID")
        return False
        
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE implemented_suggestions SET success_rating = ?, notes = ?, metrics_after = ? WHERE id = ?", 
        (
            impl_suggestion.success_rating, 
            impl_suggestion.notes, 
            json.dumps(impl_suggestion.metrics_after) if impl_suggestion.metrics_after else None, 
            impl_suggestion.id
        )
    )
    
    rows_updated = cursor.rowcount
    conn.commit()
    conn.close()
    
    return rows_updated > 0

def load_last_analysis_time(db_name: str) -> Optional[datetime]:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM metadata WHERE key = ?", ("last_analysis_time",))
    row = cursor.fetchone()
    
    conn.close()
    
    if row and row[0]:
        return datetime.fromisoformat(row[0])
    return None

def load_suggestions(db_name: str) -> List[ImprovementSuggestion]:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM suggestions")
    rows = cursor.fetchall()
    
    suggestions = []
    for row in rows:
        suggestion = ImprovementSuggestion(
            id=row[0],
            title=row[1],
            description=row[2],
            reasoning=row[3],
            expected_impact=row[4],
            confidence=row[5],
            implementation_hints=json.loads(row[6])
        )
        suggestions.append(suggestion)
    
    conn.close()
    return suggestions

def load_implemented_suggestions(db_name: str) -> List[ImplementedSuggestion]:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT i.id, i.suggestion_id, i.implementation_time, i.metrics_before, i.metrics_after, i.success_rating, i.notes,
               s.id, s.title, s.description, s.reasoning, s.expected_impact, s.confidence, s.implementation_hints
        FROM implemented_suggestions i
        JOIN suggestions s ON i.suggestion_id = s.id
    """)
    rows = cursor.fetchall()
    
    implemented_suggestions = []
    for row in rows:
        suggestion = ImprovementSuggestion(
            id=row[7],
            title=row[8],
            description=row[9],
            reasoning=row[10],
            expected_impact=row[11],
            confidence=row[12],
            implementation_hints=json.loads(row[13])
        )
        
        implemented = ImplementedSuggestion(
            id=row[0],
            suggestion=suggestion,
            implementation_time=datetime.fromisoformat(row[2]),
            metrics_before=json.loads(row[3]),
            metrics_after=json.loads(row[4]) if row[4] else None,
            success_rating=row[5],
            notes=row[6]
        )
        
        implemented_suggestions.append(implemented)
    
    conn.close()
    return implemented_suggestions

def prune_old_data(db_name: str, max_days: int = 30) -> bool:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=max_days)).isoformat()
    
    cursor.execute("DELETE FROM actions WHERE timestamp < ?", (cutoff,))
    
    cursor.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff,))
    
    conn.commit()
    conn.close()
    return True

def prune_all_data(db_name: str) -> bool:
    conn = create_connection(db_name)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM actions")
    cursor.execute("DELETE FROM metrics")
    cursor.execute("DELETE FROM suggestions")
    cursor.execute("DELETE FROM implemented_suggestions")
    conn.commit()
    conn.close()
    return True

def create_connection(db_name: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{db_name}.db")
    return conn

def create_table(conn, table_name, columns) -> None:
    cursor = conn.cursor()
    cursor.execute(f'''
                   CREATE TABLE IF NOT EXISTS {table_name}
                   ({', '.join(columns)})
                   ''')
    conn.commit()
