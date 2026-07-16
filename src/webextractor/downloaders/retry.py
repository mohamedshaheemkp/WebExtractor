from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from collections.abc import Callable


class RetryHandler:

    def __init__(
        self,
        retries: int = 3,
        delay: float = 1.0,
    ) -> None:

        self.retries = retries
        self.delay = delay

    async def run(
        self,
        func: Callable[..., Awaitable],
        *args,
        **kwargs,
    ):

        last_error = None

        for attempt in range(self.retries):

            try:
                return await func(*args, **kwargs)

            except Exception as error:

                last_error = error

                if attempt < self.retries - 1:
                    await asyncio.sleep(self.delay)

        raise last_error