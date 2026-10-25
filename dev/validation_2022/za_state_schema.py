"""Initialization placeholders are not defined forecasts; later NaNs are errors."""
def defined_floor_states(frame):
    return ~((frame.quarter == 0) & (frame.field == 'target_production'))
