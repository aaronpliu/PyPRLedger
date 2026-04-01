from pydantic import BaseModel


class ScoreRange(BaseModel):
    """Score range configuration"""

    min_value: float
    max_value: float
    description: str
    label: str


# Score mapping configuration
SCORE_MAPPING: list[ScoreRange] = [
    ScoreRange(
        min_value=0.0, max_value=0.0, description="Meaningless suggestion", label="MEANINGLESS"
    ),
    ScoreRange(min_value=1.0, max_value=2.0, description="Bad suggestion", label="BAD"),
    ScoreRange(min_value=3.0, max_value=5.0, description="No need to handle", label="OPTIONAL_LOW"),
    ScoreRange(
        min_value=6.0, max_value=8.0, description="Can apply but not required", label="GOOD_TO_HAVE"
    ),
    ScoreRange(min_value=9.0, max_value=9.0, description="Good suggestion", label="GOOD"),
    ScoreRange(min_value=10.0, max_value=10.0, description="Must apply change", label="MUST_APPLY"),
]


def get_score_description(score: float) -> str:
    """Get description for a given score value"""
    for range_config in SCORE_MAPPING:
        if range_config.min_value <= score <= range_config.max_value:
            return range_config.description
    return "Invalid score"


def get_score_label(score: float) -> str:
    """Get label for a given score value"""
    for range_config in SCORE_MAPPING:
        if range_config.min_value <= score <= range_config.max_value:
            return range_config.label
    return "INVALID"
