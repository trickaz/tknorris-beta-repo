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
import xbmc
import urllib
import urlparse
import re
import xbmcaddon
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

QUALITY_MAP = {'HD': QUALITIES.HIGH, 'LOW': QUALITIES.LOW}
BASE_URL = 'http://uflix.org'

class UFlix_Scraper(scraper.Scraper):
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
        return 'UFlix.org'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        return '[%s] %s (%s Up, %s Down) (%s/100)' % (item['quality'], item['host'], item['up'], item['down'], item['rating'])
    
    def get_sources(self, video):
        source_url=self.get_url(video)
        sources=[]
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
    
            quality=None
            match = re.search('(?:qaulity|quality):\s*<span[^>]*>(.*?)</span>', html, re.DOTALL|re.I)
            if match:
                quality = QUALITY_MAP.get(match.group(1).upper())
                
            pattern='class="btn btn-primary".*?href="([^"]+).*?[^>]+> ([^<]+).*?fa-thumbs-o-up">\s+\((\d+)\).*?\((\d+)\)\s+<i class="fa fa-thumbs-o-down'
            for match in re.finditer(pattern, html, re.DOTALL | re.I):
                url, host, up,down = match.groups()
                match = re.search('url=([^&]+)&domain=([^&]+)', url)
                if match:
                    url=match.group(1).decode('base-64')
                    host=match.group(2).decode('base-64').lower()
                    
                # skip ad match
                if host.upper()=='HDSTREAM':
                    continue
    
                up=int(up)
                down=int(down)
                source = {'multi-part': False, 'url': url, 'host': host.lower(), 'class': self, 'quality': quality, 'up': up, 'down': down, 'direct': False}
                rating=up*100/(up+down) if (up>0 or down>0) else None
                source['rating']=rating
                source['views']=up+down
                sources.append(source)
        
        return sources

    def get_url(self, video):
        return super(UFlix_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/index.php?menu=search&query=')
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
        results=[]
        
        # filter the html down to only tvshow or movie results
        if video_type in [VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE]:
            pattern='id="series".*'
            pattern2 = '<a title="Watch (.*?) Online For FREE".*?href="([^"]+)".*\((\d{1,4})\)</a>'
        else:
            pattern='id="movies".*id="series"'
            pattern2 = 'visible-sm">\s+<a\s+title="([^"]+)\s+(\d{4})".*?href="([^"]+)"'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                fragment = match.group(0)
                for match in re.finditer(pattern2, fragment):
                    result={}
                    
                    if video_type == VIDEO_TYPES.MOVIE:
                        res_title, res_year, url = match.groups('')
                    else:
                        res_title, url, res_year = match.groups('')
                        
                    if not year or year == res_year:                
                        result['title']=res_title
                        result['url']=url.replace(self.base_url,'')
                        result['year']=res_year
                        results.append(result)
            except Exception as e:
                log_utils.log('Failure during %s search: |%s|%s|%s| (%s)' % (self.get_name(), video_type, title, year, str(e)), xbmc.LOGWARNING)
        
        return results
        
    def _get_episode_url(self, show_url, video):
        episode_pattern = 'class="link"\s+href="([^"]+/show/[^"]+/season/%s/episode/%s)"' % (video.season, video.episode)
        title_pattern='class="link"\s+href="([^"]+).*?class="tv_episode_name">.*?Episode\s+\d+\s+-\s+([^<]+)'
        return super(UFlix_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern, title_pattern)
        
    def _http_get(self, url, cache_limit=8):
        return super(UFlix_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
        