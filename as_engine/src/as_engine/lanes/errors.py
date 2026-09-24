from ..kernel.errors import ASError


class LaneUnavailable(ASError):
    rule = "LANE-01"


class LaneTimeout(ASError):
    rule = "LANE-02"


class ModelSwapped(ASError):
    """The model loaded on a lane changed mid-session (LANE-05): hard stop before T0."""

    rule = "LANE-05"
