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
import datetime
import time
import xbmcaddon
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.db_utils import DB_Connection
from salts_lib.constants import QUALITIES

BASE_URL = 'http://oneclickwatch.org'

QUALITY_MAP={}
QUALITY_MAP[QUALITIES.LOW]=[' CAM ', ' TS ']
QUALITY_MAP[QUALITIES.HIGH]=['HDRIP', 'DVDRIP']
QUALITY_MAP[QUALITIES.HD]=['720', '1080', 'BLURAY', 'BRRIP']
Q_ORDER = {QUALITIES.LOW: 1, QUALITIES.HIGH: 2, QUALITIES.HD: 3}

class OneClickWatch_Scraper(scraper.Scraper):
    base_url=BASE_URL
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        self.base_url = xbmcaddon.Addon().getSetting('%s-base_url' % (self.get_name()))
    
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.MOVIE, VIDEO_TYPES.EPISODE])
    
    @classmethod
    def get_name(cls):
        return 'OneClickWatch'
    
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

            quality = None
            match = re.search('class="title">([^<]+)', html)
            if match:
                quality = self.__get_quality(video, match.group(1))
                
            pattern = '^<a\s+href="([^"]+)"\s+rel="nofollow"'
            for match in re.finditer(pattern, html, re.M):
                url=match.group(1)
                hoster={'multi-part': False, 'class': self, 'views': None, 'url': url, 'rating': None, 'quality': quality}
                hoster['host']=urlparse.urlsplit(url).hostname
                hosters.append(hoster)

        return hosters
    
    def get_url(self, video):
        url = None
        result = self.db_connection.get_related_url(video.video_type, video.title, video.year, self.get_name(), video.season, video.episode)
        if result:
            url=result[0][0]
            log_utils.log('Got local related url: |%s|%s|%s|%s|%s|' % (video.video_type, video.title, video.year, self.get_name(), url))
        else:
            select = int(xbmcaddon.Addon().getSetting('%s-select' % (self.get_name())))
            if video.video_type == VIDEO_TYPES.EPISODE:
                search_title = '%s S%02dE%02d' % (video.title, int(video.season), int(video.episode))
            else:
                search_title = '%s %s' % (video.title, video.year)
            results = self.search(video.video_type, search_title, video.year)
            if results:
                if select == 0:
                    best_result = results[0]
                else:
                    best_qorder=0
                    best_qstr=''
                    for result in results:
                        match = re.search('\[(.*)\]$', result['title'])
                        if match:
                            q_str = match.group(1)
                            quality=self.__get_quality(video, q_str)
                            #print 'result: |%s|%s|%s|%s|' % (result, q_str, quality, Q_ORDER[quality])
                            if Q_ORDER[quality]>=best_qorder:
                                if Q_ORDER[quality] > best_qorder or (quality == QUALITIES.HD and '1080' in q_str and '1080' not in best_qstr):
                                    #print 'Setting best as: |%s|%s|%s|%s|' % (result, q_str, quality, Q_ORDER[quality])
                                    best_qstr = q_str
                                    best_result=result
                                    best_qorder = Q_ORDER[quality]
                            
                url = best_result['url']
                self.db_connection.set_related_url(video.video_type, video.title, video.year, self.get_name(), url)
        return url

    def __get_quality(self, video, q_str):
        q_str.replace(video.title, '')
        q_str.replace(video.year, '')
        q_str = q_str.upper()
        # Assume movies are low quality, tv shows are high quality
        if video.video_type == VIDEO_TYPES.MOVIE:
            quality = QUALITIES.LOW
        else:
            quality = QUALITIES.HIGH
        for key in QUALITY_MAP:
            if any(q in q_str for q in QUALITY_MAP[key]):
                quality=key
        return quality

    @classmethod
    def get_settings(cls):
        settings = super(OneClickWatch_Scraper, cls).get_settings()
        name=cls.get_name()
        settings.append('         <setting id="%s-filter" type="slider" range="0,180" option="int" label="     Filter results older than (0=No Filter) (days)" default="30" visible="eq(-3,true)"/>' % (name))
        settings.append('         <setting id="%s-select" type="enum" label="     Automatically Select (Movies only)" values="Most Recent|Highest Quality" default="0" visible="eq(-4,true)"/>' % (name))
        return settings

    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/?s=')
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
        results=[]
        filter_days = datetime.timedelta(days=int(xbmcaddon.Addon().getSetting('%s-filter' % (self.get_name()))))
        today = datetime.date.today()
        pattern ='class="title"><a href="([^"]+)[^>]+>([^<]+).*?rel="bookmark">([^<]+)'
        for match in re.finditer(pattern, html, re.DOTALL):
            url, title, date_str  = match.groups('')
            if filter_days:
                try: post_date = datetime.datetime.strptime(date_str, '%B %d, %Y').date()
                except TypeError: post_date = datetime.datetime(*(time.strptime(date_str, '%B %d, %Y')[0:6])).date()
                if today - post_date > filter_days:
                    continue

            match_year = ''
            if video_type == VIDEO_TYPES.MOVIE:
                match = re.search('(.*?)\s*[\[(]?(\d{4})[)\]]?\s*(.*)', title)
                if match:
                    title, match_year, extra_title = match.groups()
                    title = '%s [%s]' % (title, extra_title)
            else:
                match_year = ''
                match = re.search('(.*?)\s*S\d+E\d+\s*(.*)', title)
                if match:
                    title, extra_title = match.groups()
                    title = '%s [%s]' % (title, extra_title)
                                
            if not year or not match_year or year == match_year:
                result={'url': url.replace(self.base_url,''), 'title': title, 'year': match_year}
                results.append(result)
        return results

    def _http_get(self, url, cache_limit=8):
        return super(OneClickWatch_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
