# standard imports
import os
from typing import Union

# lib imports
import requests


tier_map = {
    't4-sponsors': 15,
    't3-sponsors': 10,
    't2-sponsors': 5,
    't1-sponsors': 3,
}


def get_github_sponsors() -> Union[dict, False]:
    """
    Get list of GitHub sponsors.

    Returns
    -------
    Union[dict, False]
        JSON response containing the list of sponsors. False if an error occurred.
    """
    token = os.getenv("GITHUB_TOKEN")
    org_name = os.getenv("GITHUB_ORG_NAME", "LizardByte")

    graphql_url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    query = """
            query {
              organization(login: "%s") {
                sponsorshipsAsMaintainer(first: 100) {
                  edges {
                    node {
                      sponsorEntity {
                        ... on User {
                          login
                          name
                          avatarUrl
                          url
                        }
                        ... on Organization {
                          login
                          name
                          avatarUrl
                          url
                        }
                      }
                      tier {
                        name
                        monthlyPriceInDollars
                      }
                    }
                  }
                }
              }
            }
            """ % org_name

    response = requests.post(graphql_url, json={'query': query}, headers=headers)
    data = response.json()

    if 'errors' in data or 'message' in data:
        print(data)
        print('::error::An error occurred while fetching sponsors.')
        return False

    return data
