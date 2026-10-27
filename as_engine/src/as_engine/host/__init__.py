"""The hosted engine (D-299): the game as a component of a host that routes every model call.

The owner: "It needs to use the same model router and be routed BY [the host], and be compliant with
all of its rules." Hosted, the engine proposes and the host disposes: the engine says what each
model call is (host.work), which steps a turn could take and in what order they go first
(host.governor), and hands every call to the host (host.transport); the host decides which model
answers, when, with how much thinking and what sampling, what is left out to keep the turn inside
its time, where the world is kept and how it is shown. The engine holds the world in memory only
and hands it back as bytes (host.world); a branch's earlier turn is rebuilt exactly from the
answers its latest world recorded (host.fork). The host talks to the engine over JSON lines on a
child process's pipes (host.protocol, host.bridge, host.service).

Rules HOST-01..HOST-27, LANE-12. Nothing here imports a model client of its own, opens a socket or
writes a file.
"""
