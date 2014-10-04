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
import json
import urllib2
from urllib2 import HTTPError
import urllib
import hashlib
import re
import socket
import ssl
import time
import xbmc
import log_utils
from db_utils import DB_Connection
from constants import TRAKT_SECTIONS
from constants import TEMP_ERRORS
from constants import SECTIONS
from constants import TRAKT_SORT

class TraktError(Exception):
    pass

class TransientTraktError(Exception):
    pass

BASE_URL = 'api.trakt.tv'
API_KEY='db2aa092680518505621a5ddc007611c'
    
class Trakt_API():
    def __init__(self, username, password, use_https=False, timeout=5):
        self.username=username
        self.sha1password=hashlib.sha1(password).hexdigest()
        self.protocol='https://' if use_https else 'http://'
        self.timeout=timeout
        
    def valid_account(self):
        url='/account/test/%s' % (API_KEY)
        return self.__call_trakt(url, cache_limit=0)
        
    def show_list(self, slug, section, username=None, cached=True):
        if not username: 
            username = self.username
            cache_limit=0 # don't cache user's own lists at all
            cached=False
        else:
            cache_limit=1 # cache other user's list for one hour
        url='/user/list.json/%s/%s/%s' % (API_KEY, username, slug)
        list_data=self.__call_trakt(url, cache_limit=cache_limit, cached=cached)
        list_header = list_data.copy()
        del(list_header['items'])
        items=[]
        for item in list_data['items']:
            if item['type']==TRAKT_SECTIONS[section][:-1]:
                show=item[item['type']]
                show.update(self.__get_user_attributes(item))
                items.append(show)
        return (list_header, items)
    
    def show_watchlist(self, section):
        url='/user/watchlist/%s.json/%s/%s' % (TRAKT_SECTIONS[section], API_KEY, self.username)
        return self.__call_trakt(url, cache_limit=0)
    
    def get_lists(self, username=None):
        if not username: username = self.username
        url='/user/lists.json/%s/%s' % (API_KEY, username)
        return self.__call_trakt(url, cache_limit=0)
    
    def add_to_list(self, slug, items):
        return self.__manage_list('add', slug, items)
        
    def add_to_collection(self, section, item):
        return self.__manage_collection('library', section, item)
        
    def remove_from_collection(self, section, item):
        return self.__manage_collection('unlibrary', section, item)
        
    def set_watched(self, section, item, season='', episode='', watched=True):
        video_type = TRAKT_SECTIONS[section][:-1]
        if section == SECTIONS.MOVIES:
            data = {'movies': [item]}
        else:
            data = item
            if episode:
                video_type += '/episode'
                data.update({'episodes': [{'season': season, 'episode': episode}]})
            elif season:
                video_type += '/season.json'
                data.update('season', season)
            
        w_str = 'seen' if watched else 'unseen'
        url = '/%s/%s/%s' % (video_type, w_str, API_KEY)
        return self.__call_trakt(url, extra_data=data, cache_limit=0)
    
    def remove_from_list(self, slug, items):
        return self.__manage_list('delete', slug, items)
    
    def add_to_watchlist(self, section, items):
        return self.__manage_watchlist('watchlist', section, items)
        
    def remove_from_watchlist(self, section, items):
        return self.__manage_watchlist('unwatchlist', section, items)
    
    def get_trending(self, section):
        url='/%s/trending.json/%s' % (TRAKT_SECTIONS[section], API_KEY)
        return self.__call_trakt(url)
    
    def get_recommendations(self, section):
        url='/recommendations/%s/%s' % (TRAKT_SECTIONS[section], API_KEY)
        return self.__call_trakt(url)
        
    def get_friends_activity(self, section, include_episodes=False):
        if section == SECTIONS.TV:
            types='show'
            if include_episodes:
                types += ',episode'
        elif section == SECTIONS.MOVIES:
            types='movie'

        url='/activity/friends.json/%s/%s' % (API_KEY, types)
        return self.__call_trakt(url)
        
    def get_calendar(self, start_date=None, cached=True):
        url='/calendar/shows.json/%s' % (API_KEY)
        if start_date: url += '/%s' % (start_date)
        return self.__call_trakt(url, cached=cached)
    
    def get_premieres(self, start_date=None, cached=True):
        url='/calendar/premieres.json/%s' % (API_KEY)
        if start_date: url += '/%s' % (start_date)
        return self.__call_trakt(url, cached=cached)
    
    def get_my_calendar(self, start_date=None, cached=True):
        url='/user/calendar/shows.json/%s/%s' % (API_KEY, self.username)
        if start_date: url += '/%s' % (start_date)
        return self.__call_trakt(url, cached=cached)
        
    def get_seasons(self, slug):
        url = '/show/seasons.json/%s/%s' % (API_KEY, slug)
        return self.__call_trakt(url, cache_limit=8)
    
    def get_episodes(self, slug, season):
        url = '/show/season.json/%s/%s/%s' % (API_KEY, slug, season)
        return self.__call_trakt(url, cache_limit=1)
    
    def get_show_details(self, slug):
        url = '/show/summary.json/%s/%s' % (API_KEY, slug)
        return self.__call_trakt(url, cache_limit=8)
    
    def get_episode_details(self, slug, season, episode):
        url = '/show/episode/summary.json/%s/%s/%s/%s' % (API_KEY, slug, season, episode)
        return self.__call_trakt(url, cache_limit=8)
    
    def get_movie_details(self, slug):
        url = '/movie/summary.json/%s/%s' % (API_KEY, slug)
        return self.__call_trakt(url, cache_limit=8)
    
    def search(self, section, query):
        url='/search/%s.json/%s?query=%s' % (TRAKT_SECTIONS[section], API_KEY, urllib.quote_plus(query))
        return self.__call_trakt(url)
    
    def get_collection(self, section, cached=True):
        url='/user/library/%s/collection.json/%s/%s/true' % (TRAKT_SECTIONS[section], API_KEY, self.username)
        return self.__call_trakt(url, cached=cached)
    
    def get_watched(self, section, cached=True):
        url='/user/library/%s/watched.json/%s/%s/min' % (TRAKT_SECTIONS[section], API_KEY, self.username)
        return self.__call_trakt(url, cached=cached)
        
    def get_progress(self, title=None, sort=TRAKT_SORT.ACTIVITY, full=True, cached=True):
        if title is None: title='all'
        url='/user/progress/watched.json/%s/%s/%s/%s' % (API_KEY, self.username, title, sort)
        if full: url += '/full'
        return self.__call_trakt(url, cached=cached)
    
    def rate(self, section, item, rating, season='', episode=''):
        data = item
        if section == SECTIONS.MOVIES:
            rating_type = 'movie'
        else:
            if season and episode:
                rating_type = 'episode'
                data.update({'season': season, 'episode': episode})
            else:
                rating_type = 'show'
                
        url ='/rate/%s/%s' % (rating_type, API_KEY)
        data['rating']=rating
        self.__call_trakt(url, extra_data=data, cache_limit=0)
        
    def get_slug(self, url):
        pattern = 'https?://trakt\.tv/(?:show|movie)/'
        url=re.sub(pattern, '', url.lower())
        return url
    
    def __get_user_attributes(self, item):
        show={}
        if 'watched' in item: show['watched']=item['watched']
        if 'in_collection' in item: show['in_collection']=item['in_collection']
        if 'in_watchlist' in item: show['in_watchlist']=item['in_watchlist']
        if 'rating' in item: show['rating']=item['rating']
        if 'rating_advanced' in item: show['rating_advanced']=item['rating_advanced']
        return show
    
    def __manage_list(self, action, slug, items):
        url='/lists/items/%s/%s' % (action, API_KEY)
        if not isinstance(items, (list,tuple)): items=[items]
        extra_data={'slug': slug, 'items': items}
        return self.__call_trakt(url, extra_data, cache_limit=0)
    
    def __manage_watchlist(self, action, section, items):
        url='/%s/%s/%s' % (TRAKT_SECTIONS[section][:-1], action, API_KEY)
        if not isinstance(items, (list,tuple)): items=[items]
        extra_data={TRAKT_SECTIONS[section]: items}
        return self.__call_trakt(url, extra_data, cache_limit=0)
    
    def __manage_collection(self, action, section, item):
        url = '/%s/%s/%s' % (TRAKT_SECTIONS[section][:-1], action, API_KEY)
        if section == SECTIONS.TV:
            data = item
        else:
            data = {'movies': [item]}
        return self.__call_trakt(url, extra_data = data, cache_limit=0)
        
    def __call_trakt(self, url, extra_data=None, cache_limit=.25, cached=True):
        if not cached: cache_limit = 0
        data={'username': self.username, 'password': self.sha1password}
        if extra_data: data.update(extra_data)
        url = '%s%s%s' % (self.protocol, BASE_URL, url)
        log_utils.log('Trakt Call: %s, data: %s' % (url, data), xbmc.LOGDEBUG)

        db_connection = DB_Connection()
        created, cached_result = db_connection.get_cached_url(url)
        if cached_result and (time.time() - created) < (60 * 60 * cache_limit):
            result = cached_result
            log_utils.log('Returning cached result for: %s' % (url), xbmc.LOGDEBUG)
        else: 
            try:
                f=urllib2.urlopen(url, json.dumps(data), self.timeout)
                result=f.read()
                db_connection.cache_url(url, result)
            except (ssl.SSLError,socket.timeout)  as e:
                if cached_result:
                    result = cached_result
                    log_utils.log('Temporary Trakt Error (%s). Using Cached Page Instead.' % (str(e)), xbmc.LOGWARNING)
                else:
                    raise TransientTraktError('Temporary Trakt Error: '+str(e))
            except urllib2.URLError as e:
                if isinstance(e, urllib2.HTTPError):
                    if e.code in TEMP_ERRORS:
                        if cached_result:
                            result = cached_result
                            log_utils.log('Temporary Trakt Error (%s). Using Cached Page Instead.' % (str(e)), xbmc.LOGWARNING)
                        else:
                            raise TransientTraktError('Temporary Trakt Error: '+str(e))
                    elif e.code == 404:
                        return
                    else:
                        raise
                elif isinstance(e.reason, socket.timeout) or isinstance(e.reason, ssl.SSLError):
                    if cached_result:
                        result = cached_result
                        log_utils.log('Temporary Trakt Error (%s). Using Cached Page Instead' % (str(e)), xbmc.LOGWARNING)
                    else:
                        raise TransientTraktError('Temporary Trakt Error: '+str(e))
                else:
                    raise TraktError('Trakt Error: '+str(e))

        response=json.loads(result)

        if 'status' in response and response['status']=='failure':
            if 'message' in response: raise TraktError(response['message'])
            if 'error' in response: raise TraktError(response['error'])
            else: raise TraktError()
        else:
            #log_utils.log('Trakt Response: %s' % (response), xbmc.LOGDEBUG)
            return response

