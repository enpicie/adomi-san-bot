EVENT_PARTICIPANTS_QUERY = """
    query EventEntrants($slug: String) {
        event(slug: $slug) {
            id
            tournament {
                name
            }
            name
            entrants(query: {
                page: 1
                perPage: 75
            }) {
                pageInfo {
                    total
                }
                nodes {
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
