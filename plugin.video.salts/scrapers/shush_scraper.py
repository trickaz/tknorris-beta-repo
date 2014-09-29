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
import json
import base64
from salts_lib.db_utils import DB_Connection
from salts_lib import GKDecrypter
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

BASE_URL = 'http://shush.se'

class Shush_Scraper(scraper.Scraper):
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
        return 'Shush.se'
    
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
            match = re.search(',(http.*?proxy\.swf)&proxy\.link=([^&]+)', html)            
            if match:
                swf_link, proxy_link = match.groups()
                if proxy_link.startswith('http'):
                    swf_link = swf_link.replace('proxy.swf', 'pluginslist.xml')
                    html = self._http_get(swf_link, cache_limit=0)
                    match = re.search('url="(http.*?)p.swf', html)
                    if match:
                        player_url = match.group(1)
                        url = player_url + 'plugins_player.php'
                        data = {'url': proxy_link}
                        html = self._http_get(url, data=data, cache_limit=0)
                        if 'fmt_stream_map' in html:
                            sources = self.__parse_fmt(html)
                        else:
                            sources = self.__parse_fmt2(html)

                        if sources:
                            for source in sources:
                                hoster = {'multi-part': False, 'url': source, 'class': self, 'quality': sources[source], 'host': 'shush.se', 'rating': None, 'views': None}
                                hosters.append(hoster)
                else:
                    proxy_link = proxy_link.split('*', 1)[-1]
                    stream_url = GKDecrypter.decrypter(198,128).decrypt(proxy_link, base64.urlsafe_b64decode('djRBdVhhalplRm83akFNZ1VOWkI='),'ECB').split('\0')[0]
                    hoster = {'multi-part': False, 'url': stream_url, 'class': self, 'quality': QUALITIES.HIGH, 'host': urlparse.urlsplit(stream_url).hostname, 'rating': None, 'views': None}
                    hosters.append(hoster)
         
        return hosters

    def __parse_fmt(self, html):
        html = re.sub('\s', '', html)
        html = html.replace('\\u0026', '&')
        html = html.replace('\\u003d', '=')
        sources={}
        formats={}
        for match in re.finditer('\["(.*?)","(.*?)"\]', html):
            key, value = match.groups()
            if key == 'fmt_stream_map':
                items = value.split(',')
                for item in items:
                    source_fmt, source_url = item.split('|')
                    sources[source_url]=source_fmt
            elif key == 'fmt_list':
                items = value.split(',')
                for item in items:
                    format_key, q_str, _ = item.split('/', 2)
                    w,_ = q_str.split('x')
                    formats[format_key]=self.__set_quality(w)
        
        for source in sources:
            sources[source]=formats[sources[source]]
        return sources
    
    def __parse_fmt2(self, html):
        pattern='"url"\s*:\s*"([^"]+)"\s*,\s*"height"\s*:\s*\d+\s*,\s*"width"\s*:\s*(\d+)\s*,\s*"type"\s*:\s*"video/'
        sources={}
        for match in re.finditer(pattern, html):
            url, width = match.groups()
            url = url.replace('%3D', '=')
            sources[url]=self.__set_quality(width)
        return sources
            
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
        return super(Shush_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/index.php')
        if video_type == VIDEO_TYPES.MOVIE:
            search_url += '?movies'
            pattern = '<div class="shows">.*?href="([^"]+).*?alt="([^"]+) \((\d{4})\)'
        else:
            search_url += '?shows'
            pattern = '<div class="shows">.*?href="([^"]+).*?alt="(?:Watch )?([^"]+?)(?: [Oo]nline|for free)[^"]+()"'
        html = self._http_get(search_url, cache_limit=.25)
        
        results=[]
        norm_title = self._normalize_title(title)
        for match in re.finditer(pattern, html, re.DOTALL):
            url, match_title, match_year = match.groups('')
            if norm_title in self._normalize_title(match_title) and (not year or not match_year or year == match_year):
                if not url.startswith('/'): url = '/' + url
                result = {'url': url, 'title': match_title, 'year': match_year}
                results.append(result)
        return results
    
    def _get_episode_url(self, show_url, video):
        episode_pattern = '<div class="list"><a\s+href="([^"]+)"[^<]+Season\s+%s\s+Episode:\s+%s' % (video.season, video.episode)
        title_pattern= '<div class="list"><a\s+href="([^"]+)"[^<]+Season\s+1\s+Episode:\s+\d+\s+-\s+([^<]+)'
        url = super(Shush_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern, title_pattern)
        if url and not url.startswith('/'): url = '/' + url
        return url
        
    def _http_get(self, url, data=None, cache_limit=8):
        return super(Shush_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
