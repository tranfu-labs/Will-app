"""Web observability panel: a read-only projection of the event store plus an
approval inbox writer. It is NOT a control plane — it never starts runs, never
writes the event store, and never touches WillState. See docs/web-panel.md.
"""
