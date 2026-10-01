"""Live validation against the Heroku API."""


async def validate_region_live(heroku, region: str) -> bool:
    regions = await heroku.regions.list()
    return any(r["name"] == region for r in regions)


async def validate_dyno_type_live(heroku, dyno_type: str) -> bool:
    sizes = await heroku.dyno_sizes.list()
    return any(s["name"] == dyno_type for s in sizes)
