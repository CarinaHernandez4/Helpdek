from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import now


# Modulo "Registro de tiempo de atencion" (docs/Propuesta Modulo Nuevo

@dataclass
class WorkLog:
    # None hasta que el repositorio guarda el objeto: la base asigna la llave.
    id: int | None = field(default=None, kw_only=True)
    ticket_id: int
    author_id: int
    minutes: int
    note: str
    created_at: datetime = field(default_factory=now)
