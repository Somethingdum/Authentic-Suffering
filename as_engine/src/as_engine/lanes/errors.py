from ..kernel.errors import ASError


class LaneUnavailable(ASError):
    rule = "LANE-01"


class LaneTimeout(ASError):
    """A call that could not finish. Since D-110 nothing here is a wall-clock limit: the one
    subclass raised is LaneStalled (LANE-10)."""

    rule = "LANE-02"


class LaneStalled(LaneTimeout):
    """LANE-10 (D-110): the model made no progress (no token, no reasoning, no prefill advance) for
    the lane's whole stall window. A slow call that keeps moving is never this."""

    rule = "LANE-10"


class ModelSwapped(ASError):
    """The model loaded on a lane changed mid-session (LANE-05): hard stop before T0."""

    rule = "LANE-05"


class LaneRefused(ASError):
    """LANE-12: a routed transport (one whose host picks the model, D-299) could not run this call —
    no model the host may use, an error the host reported, or the call stopped there. The call fails
    with 'lane_error'; the lane is never marked down, because the host, not the engine, knows what
    is available, and the next call may well run."""

    rule = "LANE-12"


class CallSkipped(ASError):
    """LANE-12: the host left this optional call out to keep the turn inside its time (D-299). The
    call answers 'cancelled', exactly like an ablated one (LANE-09), so its caller takes the path it
    already has for a call that did not come back."""

    rule = "LANE-12"
