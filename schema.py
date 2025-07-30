from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime

class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TagCategory(str, Enum):
    WORK = "work"
    PERSONAL = "personal"
    SHOPPING = "shopping"
    COMMUNICATION = "communication"
    LEARNING = "learning"
    HEALTH = "health"
    FINANCE = "finance"
    OTHER = "other"

class TaskInput(BaseModel):
    raw_text: str = Field(..., min_length=3, description="Raw task input (min 3 chars)")
    source: Optional[str] = Field("user", description="Task source")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)

class TaskOutput(BaseModel):
    summary: str = Field(..., description="10-15 word actionable summary")
    tags: List[TagCategory] = Field(..., min_items=1, description="At least 1 tag")
    priority: PriorityLevel = Field(..., description="Priority level")
    original_text: str = Field(..., description="Original input text")
    processing_time_ms: Optional[float] = Field(None, description="Processing duration")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Confidence score")

    @validator('summary')
    def validate_summary_length(cls, v):
        words = v.split()
        if len(words) < 10 or len(words) > 15:
            raise ValueError("Summary must be 10-15 words")
        return ' '.join(words)