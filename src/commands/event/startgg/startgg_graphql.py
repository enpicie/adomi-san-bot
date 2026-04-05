FIND_SET_QUERY = """
    query FindSetBetweenEntrants($eventSlug: String, $entrantIds: [ID]) {
        event(slug: $eventSlug) {
            sets(
                page: 1
                perPage: 50
                filters: {
                    entrantIds: $entrantIds
                }
            ) {
                nodes {
                    id
                    state
                    createdAt
                    slots {
                        entrant {
                            id
                        }
                    }
                }
            }
        }
    }
"""

REPORT_SET_MUTATION = """
    mutation ReportBracketSet($setId: ID!, $winnerId: ID!, $gameData: [BracketSetGameDataInput]) {
        reportBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) {
            id
            state
        }
    }
"""

EVENT_PARTICIPANTS_QUERY = """
    query EventEntrants($slug: String) {
        event(slug: $slug) {
            id
            name
            startAt
            tournament {
                name
                venueAddress
                venueName
            }
            entrants(query: {
                page: 1
                perPage: 75
            }) {
                pageInfo {
                    total
                }
                nodes {
                    id
                    participants {
                        id
                        gamerTag
                        user {
                            authorizations(types: DISCORD) {
                                externalId
                                externalUsername
                            }
                        }
                    }
                }
            }
        }
    }
"""
