from typing import Mapping

from .base import api_function, BaseFunction
from ..request import Request
from ..session import api_session

__all__ = (
    'System',
)


class System(BaseFunction):
    """
    Provides the function interface for the API endpoint's system information.
    """

    @api_function
    @classmethod
    async def get_versions(cls) -> Mapping[str, str]:
        rqst = Request('GET', '/')
        async with rqst.fetch() as resp:
            return await resp.json()

    @api_function
    @classmethod
    async def get_manager_version(cls) -> str:
        rqst = Request('GET', '/')
        async with rqst.fetch() as resp:
            ret = await resp.json()
            return ret['manager']

    @api_function
    @classmethod
    async def get_api_version(cls) -> str:
        rqst = Request('GET', '/')
        async with rqst.fetch() as resp:
            ret = await resp.json()
            return ret['version']
