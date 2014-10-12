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
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.db_utils import DB_Connection
from salts_lib.constants import QUALITIES

BASE_URL = 'http://losmovies.tv'

class LosMovies_Scraper(scraper.Scraper):
    base_url=BASE_URL
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        self.base_url = xbmcaddon.Addon().getSetting('%s-base_url' % (self.get_name()))
    
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return 'LosMovies'
    
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
            fragment = ''
            if video.video_type == VIDEO_TYPES.EPISODE:
                pattern = 'Season\s+%s\s+Serie\s+%s</h3>(.*?)</table>' % (video.season, video.episode)
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    fragment = match.group(1)
            else:
                fragment = html
            
            if fragment:
                for match in re.finditer('data-width="([^"]+)"[^>]+>([^<]+)', fragment, re.DOTALL):
                    width, url = match.groups()
                    host = urlparse.urlsplit(url).hostname.replace('embed.','')
                    url = url.replace('&amp;', '&')
                    hoster = {'multi-part': False, 'host': host, 'class': self, 'quality': self.__set_quality(width), 'views': None, 'rating': None, 'url': url, 'direct': False}
                    hosters.append(hoster)
        return hosters

    def __set_quality(self, width):
        width=int(width)
        if width>=1280:
            quality=QUALITIES.HD
        elif width>640:
            quality=QUALITIES.HIGH
        else:
            quality=QUALITIES.MEDIUM
        return quality
    
    def get_url(self, video):
        return super(LosMovies_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/search?type=movies&q=')
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
        results=[]
        pattern ='class="movieQuality[^>]+>\s*(.*?)\s*<div\s+class="movieInfo".*?showRowImage">\s*<a\s+href="([^"]+).*?<h4[^>]+>([^<]+)'
        for match in re.finditer(pattern, html, re.DOTALL):
            match_type, url, title = match.groups('')
            if video_type == VIDEO_TYPES.TVSHOW and 'movieTV' not in match_type:
                continue
            
            r = re.search('(\d{4})$', url)
            if r:
                match_year = r.group(1)
            else:
                match_year = ''
                
            if not year or not match_year or year == match_year:
                result={'url': url.replace(self.base_url,''), 'title': title, 'year': match_year}
                results.append(result)
        return results

    def _get_episode_url(self, show_url, video):
        return show_url

    def _http_get(self, url, cache_limit=8):
        return super(LosMovies_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
