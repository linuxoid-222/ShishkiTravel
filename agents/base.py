"""Base classes for agents used in the travel bot.

Each agent implements a simple `answer` method that receives the raw user
query and a context dictionary. Agents return a small dictionary-like
object encapsulating their contribution to the final answer. Using a
common base class makes it easy to register new agents into the
orchestrator.
"""

from __future__ import annotations

from typing import Any, Dict


class AgentResult(dict):
    """A light wrapper around a dictionary to represent agent output.

    At minimum an AgentResult should contain a `type` field indicating
    the category of information it provides (e.g. "legal", "tourism").
    The `content` field holds the human-readable answer produced by the
    agent. Additional metadata can be stored as needed.
    """

    def __getattr__(self, name: str) -> Any:
        return self.get(name)


class BaseAgent:
    """Abstract base class for all agents.

    Subclasses must override the `name` attribute and implement the
    `answer` method. The orchestrator calls `answer` on each selected
    agent to produce evidence for the final response.
    """

    name: str = "base"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:
        """Process a query and return an AgentResult.

        Parameters
        ----------
        query: str
            The user's raw question.
        context: dict
            Information extracted by the orchestrator such as country,
            city, origin and destination. Agents may update the context
            if they derive new values.

        Returns
        -------
        AgentResult
            The agent's contribution to the final answer.
        """
        raise NotImplementedError("Each agent must implement the answer method")
