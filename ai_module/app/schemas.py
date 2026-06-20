"""Pydantic schemas for the Finalytics AI module."""
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class UserDocument(BaseModel):
    """An arbitrary text document supplied by the user to ground the agents."""
    name: Optional[str] = None
    content: str


class CompanyRef(BaseModel):
    """A reference to a company by CUI and/or name."""
    cui: Optional[str] = None
    company_name: Optional[str] = None
    documents: List[UserDocument] = Field(
        default_factory=list,
        description="Optional user-provided documents added to the LLM context",
    )


class ScoreRequest(CompanyRef):
    """Request a Collaboration Health Score for a company."""
    pass


class PillarScore(BaseModel):
    """One pillar of the collaboration score."""
    key: str
    label: str
    score: float = Field(..., description="Pillar score 0-100")
    weight: float = Field(..., description="Relative weight 0-1")
    reasons: List[str] = []
    data_available: bool = True


class ScoreResponse(BaseModel):
    """The full Collaboration Health Score with explainability."""
    cui: Optional[str] = None
    company_name: Optional[str] = None
    score: int = Field(..., description="Overall score 0-100")
    band: str = Field(..., description="risk band: high_risk | caution | healthy")
    pillars: List[PillarScore] = []
    positives: List[str] = []
    negatives: List[str] = []
    missing_data: List[str] = []
    data_freshness: Optional[str] = None


class AgentRequest(CompanyRef):
    """Request an AI agent assessment for a company."""
    pass


class AgentResponse(BaseModel):
    """Output of an AI agent."""
    agent: str
    cui: Optional[str] = None
    company_name: Optional[str] = None
    summary: str
    bullets: List[str] = []
    model: str
    used_llm: bool


class AskRequest(CompanyRef):
    """Free-form question about a company."""
    question: str


class AskResponse(BaseModel):
    answer: str
    cui: Optional[str] = None
    model: str
    used_llm: bool


class CompareRequest(BaseModel):
    """Compare two or more companies."""
    companies: List[CompanyRef] = Field(..., min_length=2)


class CompareItem(BaseModel):
    cui: Optional[str] = None
    company_name: Optional[str] = None
    score: int
    band: str
    positives: List[str] = []
    negatives: List[str] = []


class CompareResponse(BaseModel):
    items: List[CompareItem] = []
    ranking: List[str] = Field(..., description="CUIs/names ordered best to worst")
    recommendation: str
