from __future__ import annotations

from typing import Any


# The applications the canned database knows. It is keyed by application name -
# the name the project registry holds for a repository, which is not the
# repository slug.
MOCK_APP_NAME = "mylang"
MOCK_SECOND_APP_NAME = "mymcp"

# The refs each application has a record for. A tag carries what shipped; the
# branch carries what the walk produced at its tip.
MOCK_TAG = "1.0.0_10000"
MOCK_SECOND_TAG = "0.1.0_10000"
MOCK_BRANCH = "main"

# The shape the dependency database answers with: what the application declared
# for its modules (an exact version each), and what those modules - and the
# packages they pull in - declared for theirs (a range each).
MOCK_RELEASE_INFOS: dict[str, dict[str, dict[str, Any]]] = {
    MOCK_APP_NAME: {
        MOCK_TAG: {
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
    },
    # A second application, shaped differently: two modules over a shared core,
    # and no cycle - so the canvas of one never reads as the canvas of the other.
    MOCK_SECOND_APP_NAME: {
        MOCK_SECOND_TAG: {
            "created_at": "2026-09-28",
            "dependencies": {
                "mcpCore": "0.1.0",
                "mcpTransport": "0.2.0",
            },
            "packages": [
                {
                    "package_name": "mcpCore",
                    "version": "0.1.0",
                    "dependencies": {
                        "mcpProtocol": ">=0.1.0 <0.2.0",
                        "mcpCommon": ">=0.1.0 <0.2.0",
                    },
                },
                {
                    "package_name": "mcpTransport",
                    "version": "0.2.0",
                    "dependencies": {
                        "mcpProtocol": ">=0.1.0 <0.2.0",
                        "mcpCommon": ">=0.1.0 <0.2.0",
                    },
                },
                {
                    "package_name": "mcpProtocol",
                    "version": "0.1.3",
                    "dependencies": {"mcpCommon": ">=0.1.0 <0.2.0"},
                },
            ],
        },
        MOCK_BRANCH: {
            "created_at": "2026-10-02",
            "dependencies": {
                "mcpCore": "0.1.0",
                "mcpTransport": "0.2.0",
                "mcpConfig": "0.1.0",
            },
            "packages": [
                {
                    "package_name": "mcpCore",
                    "version": "0.1.0",
                    "dependencies": {
                        "mcpProtocol": ">=0.1.0 <0.2.0",
                        "mcpCommon": ">=0.1.0 <0.2.0",
                    },
                },
                {
                    "package_name": "mcpTransport",
                    "version": "0.2.0",
                    "dependencies": {
                        "mcpProtocol": ">=0.1.0 <0.2.0",
                        "mcpCommon": ">=0.1.0 <0.2.0",
                    },
                },
                {
                    "package_name": "mcpProtocol",
                    "version": "0.1.3",
                    "dependencies": {"mcpCommon": ">=0.1.0 <0.2.0"},
                },
                {
                    "package_name": "mcpConfig",
                    "version": "0.1.0",
                    "dependencies": {"mcpCommon": ">=0.1.0 <0.2.0"},
                },
            ],
        },
    },
}


def known_app_names() -> list[str]:
    """The applications the canned database holds a record for."""
    return list(MOCK_RELEASE_INFOS)


def release_info_for(app_name: str, tag_or_branch: str) -> dict[str, Any] | None:
    """What the database holds for one application ref, or nothing.

    The application is what the record is keyed by: a name the database does not
    know has no answer, which is how an unregistered repository reads. A ref
    without a record of its own answers with the newest one held, so the canvas
    still shows the shape of the application.
    """
    releases = MOCK_RELEASE_INFOS.get(app_name)
    if not releases:
        return None

    payload = releases.get(tag_or_branch) or next(iter(releases.values()))
    return {"app_name": app_name, "tagOrBranch": tag_or_branch, **payload}
