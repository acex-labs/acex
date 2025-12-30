from pydantic import BaseModel


class Ned(BaseModel):
    name: str
    package_name: str
    version: str
    description: str
    filename: str
