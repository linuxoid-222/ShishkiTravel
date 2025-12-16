from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

Need = Literal["tourism", "legal", "weather", "route"]

class RouteDecision(BaseModel):
    country: Optional[str] = None
    city: Optional[str] = None
    dates: Optional[str] = None
    start_location: Optional[str] = None
    end_location: Optional[str] = None
    needs: List[Need] = Field(default_factory=list)
    user_question: str = ""

class TourismPlace(BaseModel):
    name: str
    why: str
    time_needed: Optional[str] = None
    query: Optional[str] = None
    summary: Optional[str] = None
    image_url: Optional[str] = None
    maps_url: Optional[str] = None

class FoodPlace(BaseModel):
    name: str
    why: str
    query: Optional[str] = None
    maps_url: Optional[str] = None

class TourismResult(BaseModel):
    destination_title: str = ""
    overview: str = ""
    history: str = ""
    city_image_url: Optional[str] = None
    highlights: List[TourismPlace] = Field(default_factory=list)
    etiquette: List[str] = Field(default_factory=list)
    food_spots: List[FoodPlace] = Field(default_factory=list)
    areas: List[str] = Field(default_factory=list)
    plan_1_day: List[str] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)
    questions_to_clarify: List[str] = Field(default_factory=list)

class LegalResult(BaseModel):
    visa_required: Optional[bool] = None
    visa: List[str] = Field(default_factory=list)
    entry_and_registration: List[str] = Field(default_factory=list)
    prohibitions_and_fines: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    missing_info: Optional[str] = None

class WeatherResult(BaseModel):
    place: str = ""
    summary: str = ""
    now_temp_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    wind_ms: Optional[float] = None
    advice: List[str] = Field(default_factory=list)
    source: str = "openweather"

class RouteStep(BaseModel):
    instruction: str
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None

class RouteResult(BaseModel):
    start: str = ""
    end: str = ""
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    steps: List[RouteStep] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    source: str = "osrm"
    maps_url: Optional[str] = None
    points: List[str] = Field(default_factory=list)

class FinalBundle(BaseModel):
    destination_title: str
    tourism: Optional[TourismResult] = None
    legal: Optional[LegalResult] = None
    weather: Optional[WeatherResult] = None
    route: Optional[RouteResult] = None
    summary_line: Optional[str] = None
