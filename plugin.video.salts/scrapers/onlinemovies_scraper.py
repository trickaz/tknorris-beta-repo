"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import scraper
import urllib
import urlparse
import re
import xbmcaddon
import xbmc
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.db_utils import DB_Connection
from salts_lib.constants import QUALITIES

BASE_URL = 'http://onlinemovies.pro'

QUALITY_MAP={}
QUALITY_MAP[QUALITIES.LOW]=['CAM']
QUALITY_MAP[QUALITIES.HIGH]=['HDRIP']
QUALITY_MAP[QUALITIES.HD]=['720', '1080', 'BLURAY']

class OnlineMovies_Scraper(scraper.Scraper):
    base_url=BASE_URL
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        self.base_url = xbmcaddon.Addon().getSetting('%s-base_url' % (self.get_name()))
    
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return 'OnlineMovies'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        return '[%s] %s (%s views) (%s/100)' % (item['quality'], item['host'],  item['views'], item['rating'])
    
    def get_sources(self, video):
        source_url= self.get_url(video)
        hosters=[]
        if source_url:
            url = urlparse.urljoin(self.base_url,source_url)
            html = self._http_get(url, cache_limit=.5)
            match = re.search("class=\"video-embed\">\s+<iframe.*?src='([^']+)", html)
            if match:
                url=match.group(1)                
                hoster = {'multi-part': False, 'host': 'videomega.tv', 'class': self, 'quality': None, 'views': None, 'rating': None, 'url': url, 'direct': False}
                match = re.search('class="views-infos">(\d+).*?class="rating">(\d+)%', html, re.DOTALL)
                if match:
                    hoster['views']=int(match.group(1))
                    hoster['rating']=match.group(2)
                
                match = re.search('Quality.*?:(.*)<', html)
                if match:
                    q_str = match.group(1).upper()
                    q_str = q_str.replace('STRONG', '')
                    for key in QUALITY_MAP:
                        if any(q in q_str for q in QUALITY_MAP[key]):
                            hoster['quality']=key
                hosters.append(hoster)
        return hosters

    def get_url(self, video):
        return super(OnlineMovies_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/?s=')
        search_url += urllib.quote_plus('%s %s' % (title, year))
        html = self._http_get(search_url, cache_limit=.25)
        results=[]
        if not re.search('Sorry, but nothing matched', html):
            pattern ='<ul class="listing-videos(.*?)</ul>'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                fragment = match.group(1)
                pattern='href="([^"]+)"\s+title="([^"]+)'
                for match in re.finditer(pattern, fragment):
                    url, title_year = match.groups()
                    if re.search('S\d{2}E\d{2}', title_year): continue
                    match = re.search('(.*?)\s*(?:\((\d+)\)).*', title_year)
                    if match:
                        match_title, match_year = match.groups()
                    else:
                        match = re.search('(.*?)\s*(?:(\d{4}))$', title_year)
                        if match:
                            match_title, match_year = match.groups()
                        else:
                            match_title=title_year
                            match_year=''
                    if not year or not match_year or year == match_year:
                        result = {'title': match_title, 'year': match_year, 'url': url.replace(self.base_url,'')}
                        results.append(result)

        return results

    def _http_get(self, url, data=None, cache_limit=8):
        return super(OnlineMovies_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
