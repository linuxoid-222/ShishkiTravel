from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Literal, Tuple, Any

Need = Literal["tourism", "legal", "weather", "route"]

@dataclass
class UserState:
    country: Optional[str] = None
    city: Optional[str] = None
    dates: Optional[str] = None
    start_location: Optional[str] = None
    end_location: Optional[str] = None

    pending_needs: List[Need] = field(default_factory=list)
    pending_input: Optional[str] = None  # 'route_points' | 'destination'

    history: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""

    # route UI (A->B or POI)
    last_route_url: Optional[str] = None
    last_origin: Optional[Tuple[float, float]] = None
    last_dest: Optional[Tuple[float, float]] = None

    # Media cards
    media_queue: List[Dict[str, Any]] = field(default_factory=list)

    # Interactive lists
    poi_items: List[Dict[str, Any]] = field(default_factory=list)
    food_items: List[Dict[str, Any]] = field(default_factory=list)

    # Day plan cache (computed from the same POIs/food)
    day_plan_text: Optional[str] = None
    day_plan_route_url: Optional[str] = None

class StateStore:
    def __init__(self):
        self._by_user: Dict[int, UserState] = {}

    def get(self, user_id: int) -> UserState:
        if user_id not in self._by_user:
            self._by_user[user_id] = UserState()
        return self._by_user[user_id]

    def reset(self, user_id: int) -> None:
        self._by_user[user_id] = UserState()
