from dataclasses import dataclass


@dataclass
class Config:
    pandoc: str = "pandoc"
    timeout: int = 60
