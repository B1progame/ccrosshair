from __future__ import annotations


class GridHistory:
    def __init__(self) -> None:
        self._undo: list[frozenset[tuple[int, int]]] = []
        self._redo: list[frozenset[tuple[int, int]]] = []
        self._current: frozenset[tuple[int, int]] = frozenset()

    def set_initial(self, cells: set[tuple[int, int]]) -> None:
        self._undo.clear()
        self._redo.clear()
        self._current = frozenset(cells)

    def commit(self, cells: set[tuple[int, int]]) -> bool:
        new_state = frozenset(cells)
        if new_state == self._current:
            return False
        self._undo.append(self._current)
        self._current = new_state
        self._redo.clear()
        return True

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> set[tuple[int, int]] | None:
        if not self._undo:
            return None
        self._redo.append(self._current)
        self._current = self._undo.pop()
        return set(self._current)

    def redo(self) -> set[tuple[int, int]] | None:
        if not self._redo:
            return None
        self._undo.append(self._current)
        self._current = self._redo.pop()
        return set(self._current)
