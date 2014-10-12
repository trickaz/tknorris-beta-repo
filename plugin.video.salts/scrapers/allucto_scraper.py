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
import urllib2
import urlparse
import xbmcaddon
import xbmc
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES
from salts_lib.constants import USER_AGENT

QUALITY_MAP = {'DVD': QUALITIES.HIGH, 'TS': QUALITIES.MEDIUM, 'CAM': QUALITIES.LOW}
BASE_URL = 'http://dir.alluc.to'

class Alluc_Scraper(scraper.Scraper):
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
        return 'Alluc.to'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        request = urllib2.Request(url)
        request.add_header('User-Agent', USER_AGENT)
        request.add_unredirected_header('Host', request.get_host())
        request.add_unredirected_header('Referer', url)
        response = urllib2.urlopen(request)
        return response.geturl()
    
    def format_source_label(self, item):
        label='[%s] %s (%s views) (%s/100) ' % (item['quality'], item['host'], item['views'], item['rating'])
        return label
    
    def get_sources(self, video):
        source_url=self.get_url(video)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
            
            if video.video_type==VIDEO_TYPES.MOVIE:
                quality=None
            else:
                quality=QUALITIES.HIGH
            
            # extract direct links section
            match = re.search('Direct Links.*', html, re.DOTALL)
            if match:
                container = match.group()
                # extract each group
                for match in re.finditer('class="grouphosterlabel">(.*?)\s+\(\d+\)(.*?)class="folderbtn"', container, re.DOTALL):
                    host, group = match.groups()
                    host=host.lower()
                    if host == 'hqstreams':
                        continue
                    if host == 'bestreams':
                        host='bestreams.net'
                    
                    # extract links in each group
                    for match2 in re.finditer('class="openlink(?: newlink)?"\s+style="[^"]+"\s+href="([^"]+).*?Hits:\s+([.\d]+).*?name="score0"\s+value="(\d+)', group, re.DOTALL):
                        url, views, rating = match2.groups()
                        views=views.replace('.','')
                        hoster = {'multi-part': False, 'host': host.strip(), 'class': self, 'quality': quality, 'url': '/' + url, 'views': int(views), 'rating': rating, 'direct': False}
                        hosters.append(hoster)

        return hosters

    def get_url(self, video):
        return super(Alluc_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        if video_type == VIDEO_TYPES.MOVIE:
            search_url = urlparse.urljoin(self.base_url, '/movies.html')
        else:
            search_url = urlparse.urljoin(self.base_url, '/tv-shows.html')
        search_url+='?sword=%s' % (urllib.unquote_plus(title)) # only to force url cache to work
        data = {'mode': 'search', 'sword': title}
            
        results=[]
        html = self._http_get(search_url, data, cache_limit=.25)
        pattern = r'class="newlinks" href="([^"]+)" title="watch\s+(.*?)\s*(?:\((\d{4})\))?\s+online"'
        for match in re.finditer(pattern, html):
            url, match_title, match_year = match.groups('')
            if not year or not match_year or year == match_year:
                match_title = match_title.replace(r"\'","'")
                if not url.startswith('/'): url = '/' + url
                results.append({'url': url, 'title': match_title, 'year': match_year})
        return results
    
    def _get_episode_url(self, show_url, video):
        episode_pattern = 'href="([^"]+)" title="watch[^"]+Season\s+%02d\s+Episode\s+%02d\s+online' % (int(video.season), int(video.episode))
        return super(Alluc_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern)
        
    def _http_get(self, url, data=None, cache_limit=8):
        return super(Alluc_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
