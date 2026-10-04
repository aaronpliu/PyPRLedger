from __future__ import annotations

from typing import Any


MOCK_APP_NAME = "pylang"
MOCK_TAG = "1.0.0_10000"
MOCK_BRANCH = "main"

# The shape the dependency database answers with: what the application declared
# for its modules (an exact version each), and what those modules - and the
# packages they pull in - declared for theirs (a range each).
MOCK_RELEASE_INFOS: dict[str, dict[str, Any]] = {
    MOCK_TAG: {
        "app_name": MOCK_APP_NAME,
        "tagOrBranch": MOCK_TAG,
        "created_at": "2026-09-30",
        "dependencies": {
            "packageA": "1.0.0",
            "packageB": "1.0.0",
            "packageC": "1.1.0",
        },
        "packages": [
            {
                "package_name": "packageA",
                "version": "1.0.0",
                "dependencies": {"packageD": ">=1.0.0 <1.9.0"},
            },
            {
                "package_name": "packageB",
                "version": "1.0.0",
                "dependencies": {"packageE": ">=1.0.0 <1.9.0"},
            },
            {
                "package_name": "packageC",
                "version": "1.1.0",
                "dependencies": {
                    "packageD": ">=1.0.0 <1.9.0",
                    "packageE": ">=1.0.0 <1.9.0",
                },
            },
            # Not declared by the application, so it is a transitive package -
            # and it reaches back to packageA, which is the cycle on the canvas.
            {
                "package_name": "packageD",
                "version": "1.5.0",
                "dependencies": {"packageA": ">=1.0.0 <2.0.0"},
            },
        ],
    },
    MOCK_BRANCH: {
        "app_name": MOCK_APP_NAME,
        "tagOrBranch": MOCK_BRANCH,
        "created_at": "2026-10-01",
        "dependencies": {
            "packageA": "1.0.0",
            "packageB": "1.0.0",
            "packageC": "1.1.0",
            "packageF": "0.9.0",
        },
        "packages": [
            {
                "package_name": "packageA",
                "version": "1.0.0",
                "dependencies": {"packageD": ">=1.0.0 <1.9.0"},
            },
            {
                "package_name": "packageB",
                "version": "1.0.0",
                "dependencies": {"packageE": ">=1.0.0 <1.9.0"},
            },
            {
                "package_name": "packageC",
                "version": "1.1.0",
                "dependencies": {
                    "packageD": ">=1.0.0 <1.9.0",
                    "packageE": ">=1.0.0 <1.9.0",
                },
            },
            {
                "package_name": "packageD",
                "version": "1.5.0",
                "dependencies": {"packageA": ">=1.0.0 <2.0.0"},
            },
            {
                "package_name": "packageF",
                "version": "0.9.0",
                "dependencies": {"packageE": ">=0.8.0 <1.0.0"},
            },
        ],
    },
}


def release_info_for(app_name: str, tag_or_branch: str) -> dict[str, Any] | None:
    """What the database holds for one application ref, or nothing.

    The application is what the record is keyed by: a name the database does not
    know has no answer, which is how an unregistered repository reads. A ref
    without a record of its own answers with the released one, so the canvas
    still shows the shape of the application.
    """
    if app_name != MOCK_APP_NAME:
        return None

    payload = MOCK_RELEASE_INFOS.get(tag_or_branch) or MOCK_RELEASE_INFOS[MOCK_TAG]
    return {**payload, "tagOrBranch": tag_or_branch}
