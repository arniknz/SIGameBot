from __future__ import annotations

import collections.abc
import inspect
import re
import typing

Handler = typing.Callable[..., typing.Any]


class Router:
    def __init__(self) -> None:
        self._commands: dict[tuple[str, bool], Handler] = {}
        self._callbacks: dict[str, Handler] = {}
        self._callback_patterns: list[tuple[re.Pattern[str], Handler]] = []

    def command(
        self, name: str, *, private: bool = False
    ) -> collections.abc.Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self._commands[(name, private)] = func
            return func

        return decorator

    def callback(
        self, data: str
    ) -> collections.abc.Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self._callbacks[data] = func
            return func

        return decorator

    def callback_pattern(
        self, pattern: str
    ) -> collections.abc.Callable[[Handler], Handler]:
        compiled = re.compile(pattern)

        def decorator(func: Handler) -> Handler:
            self._callback_patterns.append((compiled, func))
            return func

        return decorator

    @staticmethod
    async def _call(handler: Handler, **kwargs: typing.Any) -> list:
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def dispatch_command(
        self,
        name: str,
        *,
        private: bool,
        **kwargs: typing.Any,
    ) -> list:
        handler = self._commands.get((name, private))
        if handler is None:
            return []
        return await self._call(handler, **kwargs)

    async def dispatch_callback(self, data: str, **kwargs: typing.Any) -> list:
        handler = self._callbacks.get(data)
        if handler is not None:
            return await self._call(handler, **kwargs)
        for pattern, handler in self._callback_patterns:
            match = pattern.fullmatch(data)
            if match:
                return await self._call(handler, match=match, **kwargs)
        return []
