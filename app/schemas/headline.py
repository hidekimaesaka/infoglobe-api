from pydantic import BaseModel


class Headline(BaseModel):
    region: str
    title: str
    summary: str
