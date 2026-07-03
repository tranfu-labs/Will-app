"""Web-side liaison agent.

The liaison is an interaction coordinator that helps the human inspect progress,
prepare governed commands, and route low-risk messages into the will loop. It is
not the Will Engine runtime and it never writes WillState, the event store, or
the memory economy.
"""
