"""请求体的形状。FastAPI 用这些模型检查 JSON。"""

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=200)


class LoginIn(BaseModel):
    email: str
    password: str


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class QuestionIn(BaseModel):
    question: str = Field(default="", max_length=500)
    lang: str = "zh"
    datasetId: int | None = None


class DecisionIn(BaseModel):
    action: str
    value: str | None = None


class LangIn(BaseModel):
    lang: str = "zh"


class RulesIn(BaseModel):
    rules: list = []
    lang: str = "zh"
