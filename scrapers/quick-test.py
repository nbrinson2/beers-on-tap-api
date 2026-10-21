import asyncio
from scrapers.hopclt import HopCLTScraper

async def test():
    scraper = HopCLTScraper()
    listings = await scraper.scrape(
        "https://hopclt.com/brewery/olde_mecklenburg",
        "The Olde Mecklenburg Brewery"
    )
    for l in listings:
        print(f"{l.beer_name} | {l.style} | {l.abv}%")

asyncio.run(test())