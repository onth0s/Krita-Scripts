import math
from typing import Optional


def direction_from_vector(dx: float, dy: float, deadzone_radius: float) -> Optional[str]:
    """
    Resolves an (dx, dy) offset into one of the 8 pie sectors, or ``None`` when
    the cursor sits inside the circular neutral deadzone. Pure helper used by
    ``PieMenuWidget.update_selection_from_mouse`` so sector geometry is unit-testable.
    """
    if math.hypot(dx, dy) < deadzone_radius:
        return None
    angle = math.degrees(math.atan2(dy, dx))
    if -112.5 <= angle < -67.5:
        return "N"
    if -67.5 <= angle < -22.5:
        return "NE"
    if -22.5 <= angle < 22.5:
        return "E"
    if 22.5 <= angle < 67.5:
        return "SE"
    if 67.5 <= angle < 112.5:
        return "S"
    if 112.5 <= angle < 157.5:
        return "SW"
    if angle >= 157.5 or angle < -157.5:
        return "W"
    if -157.5 <= angle < -112.5:
        return "NW"
    return None
