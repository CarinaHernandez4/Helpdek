"""22/10/2026 - Contratos (clases abstractas) de almacenamiento.

Aqui defino lo que TicketService y UserService necesitan del almacenamiento,
sin decir donde se guarda. Los servicios dependen de ESTO y no de PostgreSQL ni
de un diccionario: cambiar de implementacion es cambiar que objeto se inyecta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.models.entities import Ticket, User
from app.models.enums import TicketStatus


@dataclass(frozen=True)
class TicketQuery:
    """22/10/2026 - Filtros y pagina que le pido al repositorio (semana 14).

    Junto todos los filtros en un objeto para que la API no tenga que conocer
    SQL y para que memoria y PostgreSQL respondan exactamente la misma pregunta.
    """

    status: TicketStatus | str | None = None
    category: str | None = None
    priority: str | None = None
    assignee_id: int | None = None
    requester_id: int | None = None
    limit: int | None = None
    offset: int = 0


@dataclass(frozen=True)
class TicketPage:
    """22/10/2026 - Una pagina de tickets y cuantos hay en total con esos filtros."""

    items: list[Ticket] = field(default_factory=list)
    total: int = 0


class TicketRepository(ABC):
    """22/10/2026 - Contrato de tickets. Creci el contrato de la semana 9 con lo
    que pedi en los ejercicios de la semana 13: filtros, KPIs y transaccion."""

    @abstractmethod
    def add(self, ticket: Ticket) -> Ticket:
        """Guarda el ticket nuevo y le asigna id (en PostgreSQL lo asigna la base)."""

    @abstractmethod
    def update(self, ticket: Ticket) -> Ticket:
        """Persiste los cambios de un ticket que ya existe."""

    @abstractmethod
    def by_id(self, ticket_id: int) -> Ticket | None: ...

    @abstractmethod
    def by_category(self, category: str) -> list[Ticket]: ...

    @abstractmethod
    def list(
        self,
        *,
        status: TicketStatus | str | None = None,
        category: str | None = None,
        priority: str | None = None,
        assignee_id: int | None = None,
        requester_id: int | None = None,
    ) -> list[Ticket]: ...

    @abstractmethod
    def count_by_status(self) -> dict[str, int]:
        """Cuantos tickets hay en cada estado (para los KPIs)."""

    # 22/10/2026 - commit() y rollback() existen para scripts y ejercicios. En la
    # API NO los llama el repositorio: la unidad de trabajo (session_scope) decide.
    @abstractmethod
    def commit(self) -> None:
        """Confirma la transaccion pendiente."""

    @abstractmethod
    def rollback(self) -> None:
        """Deshace la transaccion pendiente."""

    @abstractmethod
    def search(self, query: TicketQuery) -> TicketPage:
        """Filtra, ordena (mas nuevo primero) y pagina; `total` ignora la pagina."""
        ...


class UserRepository(ABC):
    """22/10/2026 - Contrato de usuarios; los ids tambien los asigna el almacenamiento."""

    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def all(self) -> list[User]: ...

    # El hash vive en el repositorio y NO en el dataclass User: asi
    
    @abstractmethod
    def password_hash_for(self, email: str) -> str | None:
        """Hash guardado del usuario (None si el correo no existe)."""

    @abstractmethod
    def set_password_hash(self, user_id: int, password_hash: str) -> None: ...





@dataclass(frozen=True)
class WorkLogSummary:
    """09/11/2026 - Los registros de tiempo de un ticket y su total acumulado (minutos)."""

    items: list[WorkLog] = field(default_factory=list)
    total_minutes: int = 0


class WorkLogRepository(ABC):
    """09/11/2026 - Contrato del modulo "Registro de tiempo de atencion" (work logs).

    No vive dentro del agregado Ticket (como comments/history): es una seccion
    aparte que solo ve el staff, asi que el servicio la consulta bajo demanda.
    """

    @abstractmethod
    def add(self, work_log: WorkLog) -> WorkLog:
        """Guarda el registro nuevo y le asigna id (en PostgreSQL lo asigna la base)."""

    @abstractmethod
    def list_for_ticket(self, ticket_id: int) -> list[WorkLog]:
        """Registros de un ticket, del mas antiguo al mas reciente."""
