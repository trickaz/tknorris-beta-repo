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
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

QUALITY_MAP = {'DVD': QUALITIES.HIGH, 'TS': QUALITIES.MEDIUM, 'CAM': QUALITIES.LOW}
BASE_URL = 'http://merdb.cn'

class MerDB_Scraper(scraper.Scraper):
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
        return 'MerDB'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        label='[%s] %s (%s views) (%s/100)' % (item['quality'], item['host'], item['views'], item['rating'])
        if item['verified']: label = '[COLOR yellow]%s[/COLOR]' % (label)
        return label
    
    def get_sources(self, video):
        source_url=self.get_url(video)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
            
            container_pattern = r'<table[^>]+class="movie_version[ "][^>]*>(.*?)</table>'
            item_pattern = (
                r'quality_(?!sponsored|unknown|play)([^>]*)></span>.*?'
                r'url=([^&]+)&(?:amp;)?domain=([^&]+)&(?:amp;)?(.*?)'
                r'"version_veiws"> ([\d]+) views</')
            max_index=0
            max_views = -1
            for container in re.finditer(container_pattern, html, re.DOTALL | re.IGNORECASE):
                for i, source in enumerate(re.finditer(item_pattern, container.group(1), re.DOTALL)):
                    qual, url, host, parts, views = source.groups()
             
                    item = {'host': host.decode('base-64'), 'url': url.decode('base-64'), 'class': self, 'direct': False}
                    item['verified'] = source.group(0).find('star.gif') > -1
                    item['quality'] = QUALITY_MAP.get(qual.upper())
                    item['views'] = int(views)
                    if item['views'] > max_views:
                        max_index=i
                        max_views=item['views']
                        
                    if max_views> 0: item['rating'] = item['views']*100/max_views
                    else: item['rating']=None
                    pattern = r'<a href=".*?url=(.*?)&(?:amp;)?.*?".*?>(part \d*)</a>'
                    other_parts = re.findall(pattern, parts, re.DOTALL | re.I)
                    if other_parts:
                        item['multi-part'] = True
                        item['parts'] = [part[0].decode('base-64') for part in other_parts]
                    else:
                        item['multi-part'] = False
                    hosters.append(item)
            
            if max_views>0:
                for i in xrange(0,max_index):
                    hosters[i]['rating']=hosters[i]['views']*100/max_views
         
        return hosters

    def get_url(self, video):
        return super(MerDB_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        search_url = self.base_url
        if video_type in [VIDEO_TYPES.TVSHOW, VIDEO_TYPES.EPISODE]:
            search_url += '/tvshow'
            
        search_url += '/advanced_search.php?name='
        search_url += urllib.quote_plus(title)
        search_url += '&year=' + urllib.quote_plus(str(year))
        search_url += '&advanced_search=Search'
            
        html = self._http_get(search_url, cache_limit=.25)
        pattern = r'class="list_box_title.+?href="(.+?)" title="Watch (.+?)"?\(?([0-9]{4})?\)?"?>'
        results=[]
        for match in re.finditer(pattern, html):
            result={}
            url, title, year = match.groups('')
            result['url']=urlparse.urljoin('/',url)
            result['title']=title
            result['year']=year
            results.append(result)
        return results
    
    def _get_episode_url(self, show_url, video):
        episode_pattern = '"tv_episode_item".+?href="([^"]+/season-%s-episode-%s)">' % (video.season, video.episode)
        title_pattern='class="tv_episode_item".*?href="([^"]+).*?class="tv_episode_name">\s+-\s+([^<]+)'
        return super(MerDB_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern, title_pattern)
        
    def _http_get(self, url, cache_limit=8):
        return super(MerDB_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
        