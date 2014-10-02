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

BASE_URL = 'http://popcornered.com'

class Popcornered_Scraper(scraper.Scraper):
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
        return 'popcornered'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        return '[%s] %s (%s/100)' % (item['quality'], item['host'], item['rating'])
    
    def get_sources(self, video):
        source_url= self.get_url(video)
        hosters=[]
        if source_url:
            url = urlparse.urljoin(self.base_url,source_url)
            html = self._http_get(url, cache_limit=.5)
            
            match = re.search('data-video="([^"]+)', html)
            if match:
                stream_url = self.base_url + '/' + urllib.quote(match.group(1))
                hoster={'multi-part': False, 'host': 'popcornered.com', 'url': stream_url, 'class': self, 'rating': None, 'views': None, 'quality': QUALITIES.HD, 'direct': True}
                hosters.append(hoster)
            
        return hosters

    def get_url(self, video):
        return super(Popcornered_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        results=[]
        token_url = urlparse.urljoin(self.base_url, '/search_results')
        html = self._http_get(token_url, cache_limit=0)
        match = re.search('input name="_token"[^>]+value="([^"]+)', html)
        if match:
            token = match.group(1)
            search_url = urlparse.urljoin(self.base_url, '/search_results?q=')
            search_url += urllib.quote_plus(title)
            data = {'search_filter': '1', 'search_field': title, 'token': token}
            html = self._http_get(search_url, data=data, cache_limit=.25)
            pattern ='href="([^"]+)"\s+class="rates__obj-name">([^<]+).*?__vote">(\d{4})'
            for match in re.finditer(pattern, html, re.DOTALL):
                url, match_title, match_year = match.groups('')
                match_title = match_title.replace("<b class='highlight'>","")
                match_title = match_title.replace("</b>","")
                if not year or not match_year or year == match_year:
                    result={'url': url.replace(self.base_url,''), 'title': match_title, 'year': match_year}
                    results.append(result)
        else:
            log_utils.log('Unable to locate popcornered token', xbmc.LOGWARNING)
            
        return results

    def _http_get(self, url, data=None, cache_limit=8):
        return super(Popcornered_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
