""" Modulo "Registro de tiempo de atencion" (work logs).

Implementa la propuesta de docs/Propuesta Modulo Nuevo.pdf: un tecnico registra
cuantos minutos dedico a un ticket open/in_progress (con una nota obligatoria) y
el staff consulta la lista completa con el total acumulado. El solicitante no
tiene acceso a esta seccion.

Dos niveles de prueba, igual que el resto del curso:
  - TicketService sobre repositorios en memoria (rapido, sin base de datos).
  - La API completa contra PostgreSQL real (fixture `committed_db`, semana 14).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.errors import (
    PermissionDeniedError,
    TicketNotFoundError,
    ValidationError,
)
from app.main import create_app
from tests.helpers import auth_headers

# --- servicio: TicketService.add_work_log / work_logs_for ----------------------------


def _open_ticket(world, requester=None):
    return world.tickets.create(
        title="Proyector sin imagen",
        description="No enciende en el salon B2",
        category="Hardware",
        priority="Medium",
        requester=requester or world.requester,
    )


def test_staff_can_log_time_on_an_open_ticket(world):
    ticket = _open_ticket(world)

    work_log = world.tickets.add_work_log(ticket.id, world.technician, 45, "Diagnostico de red")

    assert work_log.id is not None
    assert work_log.ticket_id == ticket.id
    assert work_log.author_id == world.technician.id
    assert work_log.minutes == 45
    assert work_log.note == "Diagnostico de red"


def test_work_logs_for_lists_entries_and_the_accumulated_total(world):
    ticket = _open_ticket(world)
    world.tickets.add_work_log(ticket.id, world.technician, 30, "Primera revision")
    world.tickets.add_work_log(ticket.id, world.supervisor, 15, "Segunda revision")

    summary = world.tickets.work_logs_for(ticket.id, world.technician)

    assert [log.minutes for log in summary.items] == [30, 15]
    assert summary.total_minutes == 45


def test_a_requester_cannot_log_time(world):
    ticket = _open_ticket(world)

    with pytest.raises(PermissionDeniedError):
        world.tickets.add_work_log(ticket.id, world.requester, 10, "Intento no autorizado")


def test_a_requester_cannot_read_work_logs(world):
    ticket = _open_ticket(world)
    world.tickets.add_work_log(ticket.id, world.technician, 10, "Nota")

    with pytest.raises(PermissionDeniedError):
        world.tickets.work_logs_for(ticket.id, world.requester)


def test_cannot_log_time_on_a_ticket_that_does_not_exist(world):
    with pytest.raises(TicketNotFoundError):
        world.tickets.add_work_log(999, world.technician, 10, "Nota")


@pytest.mark.parametrize("target_status", ["resolved", "closed", "cancelled"])
def test_cannot_log_time_once_the_ticket_left_open_or_in_progress(world, target_status):
    ticket = _open_ticket(world)
    if target_status in ("resolved", "closed"):
        world.tickets.change_status(ticket.id, "in_progress", actor=world.technician)
        if target_status == "closed":
            world.tickets.change_status(ticket.id, "resolved", actor=world.technician)
    world.tickets.change_status(ticket.id, target_status, actor=world.technician)

    with pytest.raises(ValidationError) as excinfo:
        world.tickets.add_work_log(ticket.id, world.technician, 10, "Nota")

    assert excinfo.value.properties["field"] == "ticket_id"


@pytest.mark.parametrize(("minutes", "field"), [(0, "minutes"), (1441, "minutes"), (-5, "minutes")])
def test_minutes_outside_1_to_1440_are_rejected(world, minutes, field):
    ticket = _open_ticket(world)

    with pytest.raises(ValidationError) as excinfo:
        world.tickets.add_work_log(ticket.id, world.technician, minutes, "Nota")

    assert excinfo.value.properties["field"] == field


@pytest.mark.parametrize("note", ["", "   "])
def test_an_empty_note_is_rejected(world, note):
    ticket = _open_ticket(world)

    with pytest.raises(ValidationError) as excinfo:
        world.tickets.add_work_log(ticket.id, world.technician, 10, note)

    assert excinfo.value.properties["field"] == "note"


def test_a_ticket_service_without_a_work_log_repository_fails_clearly(users, ticket_repository, notifier):
    from app.services.tickets import TicketService

    service = TicketService(ticket_repository, users, notifier=notifier)  # sin work_logs=
    ticket = service.create(
        title="Sin repositorio de tiempo",
        description="d",
        category="General",
        priority="Low",
        requester=users.by_email("sofia@school.edu"),
    )
    technician = users.by_email("tomas@school.edu")

    with pytest.raises(RuntimeError):
        service.add_work_log(ticket.id, technician, 10, "Nota")


# --- API: POST/GET /api/tickets/{id}/work-logs (semana 14, fixture `committed_db`) ---

REQUESTER = auth_headers(5)  # ana@umg.edu, requester
TECHNICIAN = auth_headers(3)  # technician@example.com
OTHER_TECHNICIAN = auth_headers(6)  # carlos@umg.edu, technician


@pytest.fixture
def client(committed_db):
    with TestClient(create_app()) as test_client:
        yield test_client


def assert_error(response, status_code, code):
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"error", "message", "details"}
    assert body["error"] == code
    return body


def test_post_work_log_returns_201_with_the_logged_in_author(client):
    response = client.post(
        "/api/tickets/4/work-logs",
        headers=TECHNICIAN,
        json={"minutes": 25, "note": "Revision de wifi lab 2"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ticket_id"] == 4
    assert body["author_id"] == 3
    assert body["minutes"] == 25
    assert body["note"] == "Revision de wifi lab 2"


def test_get_work_logs_returns_the_seeded_entries_and_the_total(client):
    # Ticket 2 (seed.sql) ya trae dos registros de tiempo del tecnico 3: 30 + 20 = 50.
    response = client.get("/api/tickets/2/work-logs", headers=TECHNICIAN)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total_minutes"] == 50


def test_get_reflects_a_work_log_just_created(client):
    client.post("/api/tickets/4/work-logs", headers=TECHNICIAN, json={"minutes": 25, "note": "Revision"})

    response = client.get("/api/tickets/4/work-logs", headers=OTHER_TECHNICIAN)

    assert response.json() == {
        "items": [
            {
                "id": response.json()["items"][0]["id"],
                "ticket_id": 4,
                "author_id": 3,
                "minutes": 25,
                "note": "Revision",
                "created_at": response.json()["items"][0]["created_at"],
            }
        ],
        "total_minutes": 25,
    }


def test_requester_gets_403_on_post(client):
    response = client.post(
        "/api/tickets/4/work-logs", headers=REQUESTER, json={"minutes": 10, "note": "Nota"}
    )

    assert_error(response, 403, "permission_denied")


def test_requester_gets_403_on_get(client):
    response = client.get("/api/tickets/2/work-logs", headers=REQUESTER)

    assert_error(response, 403, "permission_denied")


def test_post_without_identity_is_401(client):
    response = client.post("/api/tickets/4/work-logs", json={"minutes": 10, "note": "Nota"})

    assert_error(response, 401, "unauthenticated")


def test_post_on_a_missing_ticket_is_404(client):
    response = client.post(
        "/api/tickets/999/work-logs", headers=TECHNICIAN, json={"minutes": 10, "note": "Nota"}
    )

    body = assert_error(response, 404, "ticket_not_found")
    assert body["details"] == {"ticket_id": 999}


def test_post_on_a_closed_ticket_is_422(client):
    # Ticket 3 (seed.sql) ya esta closed.
    response = client.post(
        "/api/tickets/3/work-logs", headers=TECHNICIAN, json={"minutes": 10, "note": "Nota"}
    )

    body = assert_error(response, 422, "validation_error")
    assert body["details"]["field"] == "ticket_id"
    assert body["details"]["status"] == "closed"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"minutes": 0, "note": "Nota"}, "minutes"),
        ({"minutes": 1441, "note": "Nota"}, "minutes"),
        ({"minutes": 10, "note": ""}, "note"),
        ({"minutes": "diez", "note": "Nota"}, "minutes"),
    ],
)
def test_post_with_invalid_data_is_422(client, payload, field):
    response = client.post("/api/tickets/4/work-logs", headers=TECHNICIAN, json=payload)

    body = assert_error(response, 422, "validation_error")
    assert [error["field"] for error in body["details"]["errors"]] == [field]


def test_get_on_a_missing_ticket_is_404(client):
    response = client.get("/api/tickets/999/work-logs", headers=TECHNICIAN)

    assert_error(response, 404, "ticket_not_found")
