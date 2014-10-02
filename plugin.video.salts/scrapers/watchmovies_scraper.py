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

BASE_URL = 'http://watchmovies.to'

class WatchMovies_Scraper(scraper.Scraper):
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
        return 'WatchMovies'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        html = self._http_get(url, cache_limit=.5)
        match = re.search('href="([^"]+)', html)
        if match:
            return match.group(1)
        else:
            match = re.search('iframe src="([^"]+)', html)
            if match:
                return match.group(1)
            
    
    def format_source_label(self, item):
        label='[%s] %s (%s Views) (%s/100)' % (item['quality'], item['host'], item['views'], item['rating'])
        return label
    
    def get_sources(self, video):
        source_url=self.get_url(video)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
            
            pattern = 'switchMirror\(event,\d+,(\d+),(\d+),this\);[^>]+>(?:<img[^>]+>)?\s*([^<]+).*?Hits:</strong>\s*(\d+)'
            for match in re.finditer(pattern, html, re.DOTALL):
                video_id, hoster_num, host, views = match.groups()
                hoster_url = '%s/ajax/mirror/id=%s&hoster=%s' % (self.base_url, video_id, hoster_num)
                hoster = {'multi-part': False, 'host': host, 'class': self, 'quality': None, 'views': views, 'rating': None, 'url': hoster_url, 'direct': False}
                hosters.append(hoster)

        return hosters

    def get_url(self, video):
        return super(WatchMovies_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/search/title=')
        search_url += urllib.quote_plus(title)        
        html = self._http_get(search_url, cache_limit=.25)

        results=[]
        pattern = r'href="([^"]+)"\s+title="([^"]+)"\s+class="tooltip"'
        for match in re.finditer(pattern, html):
            url, title = match.groups('')
            if (video_type == VIDEO_TYPES.MOVIE and '/tv-shows/' in url) or (video_type == VIDEO_TYPES.TVSHOW and '/movies/' in url):
                continue
             
            result={'url': url.replace(self.base_url,''), 'title': title, 'year': ''}
            results.append(result)
        return results
    
    def _get_episode_url(self, show_url, video):
        episode_pattern = 'value="([^"]+/tv-shows/[^/]+/season-%02d-episode-%02d)' % (int(video.season), int(video.episode))
        title_pattern='value="([^"]+)"\s*>S\d+E\d+\s+([^<]+)'
        return super(WatchMovies_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern, title_pattern)
        
    def _http_get(self, url, data=None, cache_limit=8):
        return super(WatchMovies_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
