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
import re
import urllib
import urlparse
import xbmcaddon
import xbmc
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

BASE_URL = 'http://www.oneclickmoviez.ag'

class OneClick_Scraper(scraper.Scraper):
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
        return 'OneClickMoviez'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        label='[%s] %s (%s views) (%s/100) ' % (item['quality'], item['host'], item['views'], item['rating'])
        return label
    
    def get_sources(self, video):
        source_url=self.get_url(video)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
            match = re.search('id="link_list"(.*)', html, re.DOTALL)
            if match:
                fragment = match.group(1)
                pattern ='id="selector\d+"><span>([^<]+).*?href="([^"]+)'
                for match in re.finditer(pattern, fragment, re.DOTALL):
                    host, url = match.groups()
                    hoster = {'multi-part': False, 'host': host.strip(), 'class': self, 'quality': None}
                    hoster['url']= url
                    hoster['views']=None
                    hoster['rating']=None
                    hosters.append(hoster)
         
        return hosters

    def get_url(self, video):
        return super(OneClick_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/index.php?menu=search&query=')
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
        if video_type == VIDEO_TYPES.MOVIE:
            pattern='Movie results for:(.*?)(?:END MAIN CONTENT|TV show results for)'
        else:
            pattern='TV show results for:(.*)'
        
        results=[]
        match = re.search(pattern, html, re.DOTALL)
        if match:
            container = match.group(1)
            pattern='class="link"\s+href="([^"]+)"\s+title="\s*([^"]+)'
            for match in re.finditer(pattern, container):
                url, title = match.groups()
                result = {'url': url.replace(self.base_url, ''), 'title': title, 'year': ''}
                results.append(result)
        return results
    
    def _get_episode_url(self, show_url, season, episode, ep_title):
        episode_pattern = 'class="link"\s+href="([^"]+/season/%s/episode/%s)"' % (season, episode)
        return super(OneClick_Scraper, self)._default_get_episode_url(show_url, season, episode, ep_title, episode_pattern)
        
    def _http_get(self, url, cache_limit=8):
        return super(OneClick_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
