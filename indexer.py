import asyncio
import json
from typing import Dict, List, cast

import aiohttp
import requests

from exceptions import BadSearchError

WIKI_API = 'https://ru.wikipedia.org/w/api.php'


class Indexer:
    def __init__(self, page_name):
        self.session = requests.session()
        self.linked_pages: List[Dict[str, str]] = []  # List[level, Dict[page id, page data]]

        self.main_name = page_name
        try:
            self.main_id = self.get_page_id()
        except BadSearchError as e:
            print(e)
            return
        print('main id', self.main_id)

    def get_direct_linked_page(self):
        return self.get_linked_page(self.main_id)

    def start_research(self, *, max_level: int = None):
        if not len(self.linked_pages):
            self.linked_pages.clear()
            self.linked_pages.append(self.get_direct_linked_page())

        self.linked_pages = self.linked_pages[:1]
        viewed_pages = {page_id for page_id in self.linked_pages[0]}

        while len(self.linked_pages[-1]):
            if max_level is not None and len(self.linked_pages) == max_level:
                break

            last_level: Dict[str, str] = self.linked_pages[-1]
            new_level: Dict[str, str] = {}

            for page_id in last_level:
                pages = self.get_linked_page(page_id)
                for p_id, p_data in pages.items():
                    if p_id not in viewed_pages:
                        viewed_pages.add(p_id)
                        new_level[p_id] = p_data

            self.linked_pages.append(new_level)
            print(f'Level {len(self.linked_pages)} size {len(self.linked_pages[-1])}')

    def get_linked_page(self, page_id: str) -> Dict:
        """ Return Dict[page id, page name] of pages that link in page_id """
        pages = {}
        lhcontinue = 0

        while lhcontinue is not None:
            params = {
                'action': 'query',
                'format': 'json',
                'prop': 'linkshere',
                'lhshow': '!redirect',
                'lhnamespace': 0,
                'lhlimit': 500,
                'lhcontinue': lhcontinue,
                'pageids': page_id
            }
            res = self.session.get(WIKI_API, params=params)
            d = json.loads(res.text)

            if 'continue' in d:
                lhcontinue = d['continue']['lhcontinue']
            else:
                lhcontinue = None

            if 'linkshere' in d['query']['pages'][page_id]:
                for page in d['query']['pages'][page_id]['linkshere']:
                    pages[str(page['pageid'])] = {
                        'from': page['title'],
                        'to': d['query']['pages'][page_id]['title']
                    }
        return pages

    async def async_get_linked_page(self, page_id: str, session: aiohttp.ClientSession, pages: Dict):
        """ Async method for geting linked page """

        lhcontinue = 0
        while lhcontinue is not None:
            params = {
                'action': 'query',
                'format': 'json',
                'prop': 'linkshere',
                'lhshow': '!redirect',
                'lhnamespace': 0,
                'lhlimit': 500,
                'lhcontinue': lhcontinue,
                'pageids': page_id
            }

            async with session.get(WIKI_API, params=params) as res:
                data = await res.text()
                data = cast(Dict, json.loads(data))

                if 'continue' in data:
                    lhcontinue = data['continue']['lhcontinue']
                else:
                    lhcontinue = None

                if 'linkshere' in data['query']['pages'][page_id]:
                    for page in data['query']['pages'][page_id]['linkshere']:
                        pages[str(page['pageid'])] = {
                            'from': page['title'],
                            'to': data['query']['pages'][page_id]['title']
                        }

    def start_research_async(self, *, max_level: int = None):
        async def research_task(page_id, session, n_level, v_pages, i):
            pages = {}
            await asyncio.sleep(i / 100)
            is_good = False
            while not is_good:
                try:
                    await self.async_get_linked_page(page_id, session, pages)
                except json.decoder.JSONDecodeError:
                    print('Too much requests ', i)
                    return
                is_good = True

            for p_id, p_data in pages.items():
                if p_id not in v_pages:
                    v_pages.add(p_id)
                    n_level[p_id] = p_data

        async def research(l_level, n_level, v_pages):
            tasks = []
            session = aiohttp.ClientSession()
            i = 1
            for page_id in l_level:
                tasks.append(asyncio.create_task(research_task(page_id, session, n_level, v_pages, i)))
                i += 1

            await asyncio.gather(*tasks)
            await session.close()

        if not len(self.linked_pages):
            self.linked_pages.clear()
            self.linked_pages.append(self.get_direct_linked_page())

        self.linked_pages = self.linked_pages[:1]
        viewed_pages = {page_id for page_id in self.linked_pages[0]}

        while len(self.linked_pages[-1]):
            if max_level is not None and len(self.linked_pages) == max_level:
                break
            print(f'Level {len(self.linked_pages) + 1}')

            last_level: Dict[str, str] = self.linked_pages[-1]
            new_level: Dict[str, str] = {}

            asyncio.run(research(last_level, new_level, viewed_pages), debug=False)

            self.linked_pages.append(new_level)
            print(f'Level {len(self.linked_pages)} size {len(self.linked_pages[-1])}')

    def get_page_id(self, page_name: str = None) -> str:
        """ Return pageid of page by name """

        if page_name is None:
            page_name = self.main_name

        params = {
            'action': 'opensearch',
            'format': 'json',
            'search': page_name
        }
        res = self.session.get(WIKI_API, params=params)
        res = json.loads(res.text)

        try:
            page_name = res[1][0]
        except IndexError:
            raise BadSearchError

        params = {
            'action': 'query',
            'format': 'json',
            'prop': 'info',
            'titles': page_name
        }
        res = self.session.get(WIKI_API, params=params)
        res = json.loads(res.text)
        return list(res['query']['pages'].keys())[0]

    def save(self, file_name):
        with open(file_name, mode='w', encoding='utf-8') as file:
            json.dump(self.linked_pages, file, ensure_ascii=False)

    def save_last_level(self, file_name):
        with open(file_name, mode='w', encoding='utf-8') as file:
            json.dump(self.linked_pages[-1], file, ensure_ascii=False)
