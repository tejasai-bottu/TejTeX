from dataclasses import dataclass


@dataclass
class Config:
    pandoc: str = "pandoc"
    timeout: int = 60
    memory: int = 2048
    depth: int = 16
    files: int = 256
    size: int = 20_000_000
    root: str = None
