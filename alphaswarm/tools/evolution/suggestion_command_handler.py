from typing import Optional   
import re

class SuggestionCommandHandler:
    def __init__(self, evolution_agent):
        self.agent = evolution_agent
        
        self.commands = {
            "help": self._cmd_help,
            "list": self._cmd_list_suggestions,
            "implement": self._cmd_implement_suggestion,
            "status": self._cmd_suggestion_status,
            "rate": self._cmd_rate_suggestion,
            "prune": self._cmd_prune_data,
        }
    
    def process_command(self, message: str) -> Optional[str]:
        command_match = re.match(r'^\s*!suggestion\s+(\w+)(?:\s+(.+))?$', message, re.IGNORECASE)
        if not command_match:
            return None
            
        cmd = command_match.group(1).lower().strip()
        args = command_match.group(2) if command_match.group(2) else ""
        
        if cmd in self.commands:
            return self.commands[cmd](args)
        else:
            return (
                f"Unknown suggestion command: {cmd}\n"
                "Use !suggestion help for available commands."
            )
    
    def _cmd_help(self, args: str) -> str:
        return (
            "Suggestion Management Commands:\n"
            "  !suggestion list - List all recent suggestions\n"
            "  !suggestion implement <num> [notes] - Mark suggestion as implemented\n"
            "  !suggestion status - Show status of implemented suggestions\n"
            "  !suggestion rate <num> <rating> [notes] - Rate implemented suggestion (0-1)\n"
            "  !suggestion prune - Prune all data (irreversible)\n"
            "  !suggestion help - Show this help message\n"
        )
    
    def _cmd_list_suggestions(self, args: str) -> str:
        if not self.agent.last_suggestions:
            return "No recent improvement suggestions available."
            
        result = ["Recent Improvement Suggestions:"]
        result.append("-" * 40)
        for i, suggestion in enumerate(self.agent.last_suggestions):
            result.append(f"{i+1}. {suggestion.title} (confidence: {suggestion.confidence:.2f})")
            result.append(f"   {suggestion.description}")
            result.append(f"   Expected impact: {suggestion.expected_impact}")
            result.append(f"   Implementation hints: {suggestion.implementation_hints}")
            result.append(f"   Reasoning: {suggestion.reasoning}")
            result.append("-" * 40)
            
        return "\n".join(result)
    
    def _cmd_implement_suggestion(self, args: str) -> str:
        parts = args.split(maxsplit=1)
        if not parts:
            return "Usage: !suggestion implement <num> [notes]"
            
        try:
            suggestion_num = int(parts[0])
            notes = parts[1] if len(parts) > 1 else None
        except ValueError:
            return "Invalid suggestion number. Use !suggestion list to see available suggestions."
            
        suggestion_index = suggestion_num - 1
        
        result = self.agent.implement_suggestion(suggestion_index, notes)
        if not result:
            return f"Error: Suggestion #{suggestion_num} not found. Use !suggestion list to see available suggestions."
            
        return f"Suggestion #{suggestion_num} marked as implemented. Use !suggestion status to track its impact."
    
    def _cmd_suggestion_status(self, args: str) -> str:
        if not self.agent.implemented_suggestions:
            return "No suggestions have been implemented yet."
            
        result = ["Implemented Suggestions Status:"]
        result.append("-" * 40)
        for i, impl in enumerate(self.agent.implemented_suggestions):
            result.append(f"{i+1}. {impl.suggestion.title}")
            result.append(f"   Implemented on: {impl.implementation_time}")
            
            if impl.metrics_after:
                result.append("   Impact on metrics:")
                for metric, before in impl.metrics_before.items():
                    if metric in impl.metrics_after:
                        after = impl.metrics_after[metric]
                        change = after - before
                        result.append(f"     {metric}: {before:.2f} → {after:.2f} ({change:+.2f})")
            
            if impl.success_rating is not None:
                result.append(f"   Success rating: {impl.success_rating:.2f}/1.0")
                
            result.append("-" * 40)
            
        return "\n".join(result)
    
    def _cmd_rate_suggestion(self, args: str) -> str:
        parts = args.split(maxsplit=2)
        if len(parts) < 2:
            return "Usage: !suggestion rate <num> <rating> [notes]"
            
        try:
            impl_num = int(parts[0])
            rating = float(parts[1])
            notes = parts[2] if len(parts) > 2 else None
        except ValueError:
            return "Invalid number format. Please use numbers for the suggestion index and rating (0-1)."
            
        impl_index = impl_num - 1

        if impl_index < 0 or impl_index >= len(self.agent.implemented_suggestions):
            return f"Error: Implemented suggestion #{impl_num} not found."
        
        if notes:
            self.agent.implemented_suggestions[impl_index].notes = notes

        if not self.agent.analyze_suggestion_impact(impl_index, rating):
            return f"Error: Failed to update implemented suggestion #{impl_num}. ID may be missing."
            
        return f"Suggestion #{impl_num} rated successfully with score {rating:.2f}/1.0"
        
    def _cmd_prune_data(self, args: str) -> str:
        self.agent.prune_all_data(self.agent.db_name)
        return "All data has been pruned."