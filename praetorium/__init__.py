"""Thin, server-rendered Legion operations UI backed only by Aquila."""

from .wsgi import PraetoriumWSGIApp

__all__ = ["PraetoriumWSGIApp"]
