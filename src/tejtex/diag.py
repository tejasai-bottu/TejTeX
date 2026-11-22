from dataclasses import dataclass, field

CATS = ("supported", "partial", "unsupported", "render")


@dataclass
class Diag:
    level: str
    category: str
    element: str
    message: str
    loc: str = ""

    def __str__(self):
        s = f"{self.element}: {self.message}"
        if self.category:
            s += f" [{self.category}]"
        return f"{self.loc}: {s}" if self.loc else s


@dataclass
class Report:
    diags: list = field(default_factory=list)
    elements: dict = field(default_factory=dict)

    def add(self, level, category, element, message, loc=""):
        self.diags.append(Diag(level, category, element, message, loc))

    def count(self, name, category):
        e = self.elements.setdefault(name, {"category": category, "count": 0})
        e["count"] += 1
