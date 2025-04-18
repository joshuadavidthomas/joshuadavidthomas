# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "environs>=14.1.1",
#     "python-graphql-client>=0.4.3",
#     "typer>=0.15.2",
# ]
# ///
from __future__ import annotations

import re
from pathlib import Path

import environs
from python_graphql_client.graphql_client import GraphqlClient
from typer import Typer

cli = Typer()

env = environs.Env()
GITHUB_TOKEN = env.str("GITHUB_TOKEN")


BASE_DIR = Path(__file__).parent.resolve()
README = BASE_DIR / "README.md"


SKIP_REPOS = {
    "pytest-rich",
}
RELEASES_QUERY = """
query {
  search(first: 100, type: REPOSITORY, query:"is:public owner:joshuadavidthomas owner:westerveltco sort:updated", after: AFTER) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      __typename
      ... on Repository {
        name
        description
        url
        releases(orderBy: {field: CREATED_AT, direction: DESC}, first: 1) {
          totalCount
          nodes {
            name
            publishedAt
            url
          }
        }
      }
    }
  }
}
"""


def fetch_releases(oauth_token: str):
    client = GraphqlClient(endpoint="https://api.github.com/graphql")

    releases: list[dict[str, str]] = []
    repo_names = set(SKIP_REPOS)
    has_next_page = True
    after_cursor = None

    while has_next_page:
        data = client.execute(
            query=RELEASES_QUERY.replace(
                "AFTER", f'"{after_cursor}"' if after_cursor else "null"
            ),
            headers={
                "Authorization": f"Bearer {oauth_token}",
            },
        )
        repo_nodes = data["data"]["search"]["nodes"]
        for repo in repo_nodes:
            if repo["releases"]["totalCount"] and repo["name"] not in repo_names:
                repo_names.add(repo["name"])
                releases.append(
                    {
                        "repo": repo["name"],
                        "repo_url": repo["url"],
                        "description": repo["description"],
                        "release": repo["releases"]["nodes"][0]["name"]
                        .replace(repo["name"], "")
                        .strip(),
                        "published_at": repo["releases"]["nodes"][0]["publishedAt"],
                        "published_day": repo["releases"]["nodes"][0][
                            "publishedAt"
                        ].split("T")[0],
                        "url": repo["releases"]["nodes"][0]["url"],
                        "total_releases": repo["releases"]["totalCount"],
                    }
                )
        after_cursor = data["data"]["search"]["pageInfo"]["endCursor"]
        has_next_page = after_cursor

    return releases


RELEASES_SECTION = re.compile(
    r"<!\-\- releases start \-\->.*<!\-\- releases end \-\->",
    re.DOTALL,
)


@cli.command()
def main() -> None:
    with open(README) as f:
        readme = f.read()

    releases = fetch_releases(GITHUB_TOKEN)
    releases.sort(key=lambda r: r["published_at"], reverse=True)

    releases_md = "\n".join(
        ["<!-- releases start -->"]
        + [
            "* [{repo} {release}]({url}) - {published_day}".format(**release)
            for release in releases[:10]
        ]
        + ["<!-- releases end -->"]
    )

    updated_readme = RELEASES_SECTION.sub(releases_md, readme)

    with open(README, "w") as f:
        f.write(updated_readme)


if __name__ == "__main__":
    cli()
