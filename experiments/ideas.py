"""Idea sets. All map to the tip_splitter template (T1) so the A/B compares prompts, not templates.
The held-out set is never shown to the Flight Recorder or used to pick patches."""

TUNING = [
    "A tip splitter for friends sharing a restaurant bill",
    "A tool for roommates to split a shared grocery receipt including a tip for delivery",
    "A bar tab splitter for a night out with coworkers",
    "A taxi fare and tip splitter for a group airport ride",
    "A wedding dinner table bill splitter with service charge",
]

HELD_OUT = [
    "A coffee-run tip calculator for an office team",
    "A group brunch bill splitter with a suggested tip percentage",
    "A food-truck festival tab splitter for a family",
    "A hairdresser tip splitter for a salon team pool",
    "A tour guide tip pool calculator for a travel group",
]
