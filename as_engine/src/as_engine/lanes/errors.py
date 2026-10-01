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
