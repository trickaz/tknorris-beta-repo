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

BASE_URL = 'http://www.simplymovies.net'

class SimplyMovies_Scraper(scraper.Scraper):
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
        return 'SimplyMovies'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        label='[%s] %s (%s/100) ' % (item['quality'], item['host'], item['rating'])
        return label
    
    def get_sources(self, video):
        source_url=self.get_url(video)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
            pattern='class="videoPlayerIframe"\s+src="([^"]+)'
            match = re.search(pattern, html)
            if match:
                hoster={'multi-part': False, 'host': 'vk.com', 'url': match.group(1), 'class': self, 'rating': None, 'views': None, 'direct': False}
                # episodes seem to be consistently available in HD, but movies only in SD
                if video.video_type==VIDEO_TYPES.EPISODE:
                    hoster['quality']=QUALITIES.HD
                else:
                    hoster['quality']=QUALITIES.HIGH
                hosters.append(hoster)
        return hosters

    def get_url(self, video):
        return super(SimplyMovies_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        search_url = self.base_url
        if video_type in [VIDEO_TYPES.TVSHOW, VIDEO_TYPES.EPISODE]:
            search_url += '/tv_shows.php'
        else:
            search_url += '/index.php'
        search_url += '?searchTerm=%s&sort=added&genre=' % (urllib.quote_plus(title))
            
        html = self._http_get(search_url, cache_limit=.25)
        pattern = r'class="movieInfoOverlay">\s+<a\s+href="([^"]+).*?class="overlayMovieTitle">\s*([^<]+)(?:.*?class="overlayMovieRelease">.*?(\d{4})<)?'
        results=[]
        norm_title = self._normalize_title(title)
        for match in re.finditer(pattern, html, re.DOTALL):
            url, match_title, match_year = match.groups('')
            match_title=match_title.strip()
            if norm_title in self._normalize_title(match_title) and (match_year == '0001' or not year or not match_year or year == match_year):
                url = '/'+url if not url.startswith('/') else url
                result = {'url': url, 'title': match_title, 'year': match_year}
                results.append(result)
        return results
    
    def _get_episode_url(self, show_url, video):
        url = urlparse.urljoin(self.base_url, show_url)
        html = self._http_get(url, cache_limit=2)
        pattern='h3>Season\s+%s(.*?)(?:<h3>|</div>)' % (video.season)
        match = re.search(pattern, html, re.DOTALL)
        if match:
            container=match.group(1)
            pattern='href="([^"]+)">Episode %s(?:|<)' % (video.episode)
            match = re.search(pattern, container, re.DOTALL)
            if match:
                url=match.group(1)
                url = '/'+url if not url.startswith('/') else url
                return url
        
    def _http_get(self, url, cache_limit=8):
        return super(SimplyMovies_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
