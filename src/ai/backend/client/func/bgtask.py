from typing import Union
from uuid import UUID

from .base import BaseFunction
from ..request import (
    Request,
    SSEContextManager,
)
from ..session import api_session


class BackgroundTask(BaseFunction):
    """
    Provides server-sent events streaming functions.
    """

    task_id: UUID

    def __init__(self, task_id: Union[UUID, str]) -> None:
        self.task_id = task_id if isinstance(task_id, UUID) else UUID(task_id)

    # only supported in AsyncAPISession
    def listen_events(self) -> SSEContextManager:
        """
        Opens an event stream of the background task updates.

        :returns: a context manager that returns an :class:`SSEResponse` object.
        """
        params = {
            'task_id': str(self.task_id),
        }
        request = Request(
            'GET', '/events/background-task',
            params=params,
        )
        return request.connect_events()
