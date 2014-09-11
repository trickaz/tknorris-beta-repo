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
import sys
import os
import re
import datetime
import time
import xbmcplugin
import xbmcgui
import xbmc
import xbmcvfs
from addon.common.addon import Addon
from salts_lib.db_utils import DB_Connection
from salts_lib.url_dispatcher import URL_Dispatcher
from salts_lib.srt_scraper import SRT_Scraper
from salts_lib.trakt_api import Trakt_API, TransientTraktError
from salts_lib import utils
from salts_lib import log_utils
from salts_lib.constants import *
from scrapers import * # import all scrapers into this namespace

_SALTS = Addon('plugin.video.salts', sys.argv)
ICON_PATH = os.path.join(_SALTS.get_path(), 'icon.png')
VALID_ACCOUNT=utils.valid_account()
username=_SALTS.get_setting('username')
password=_SALTS.get_setting('password')
use_https=_SALTS.get_setting('use_https')=='true'
trakt_timeout=int(_SALTS.get_setting('trakt_timeout'))

trakt_api=Trakt_API(username,password, use_https, trakt_timeout)
url_dispatcher=URL_Dispatcher()
db_connection=DB_Connection()

global urlresolver

@url_dispatcher.register(MODES.MAIN)
def main_menu():
    db_connection.init_database()
    if not VALID_ACCOUNT:
        remind_count = int(_SALTS.get_setting('remind_count'))
        remind_max=5
        if remind_count<remind_max:
            remind_count += 1
            log_utils.log('Showing Config reminder')
            builtin = 'XBMC.Notification(%s,(%s/%s) Configure Trakt Account for more options, 7500, %s)'
            xbmc.executebuiltin(builtin % (_SALTS.get_name(), remind_count, remind_max, ICON_PATH))
            _SALTS.set_setting('remind_count', str(remind_count))
    else:
        _SALTS.set_setting('remind_count', '0')

    _SALTS.add_directory({'mode': MODES.BROWSE, 'section': SECTIONS.MOVIES}, {'title': 'Movies'})
    _SALTS.add_directory({'mode': MODES.BROWSE, 'section': SECTIONS.TV}, {'title': 'TV Shows'})
    _SALTS.add_directory({'mode': MODES.SCRAPERS}, {'title': 'Scraper Settings'})
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.BROWSE, ['section'])
def browse_menu(section):
    section_label='TV Shows' if section==SECTIONS.TV else 'Movies'
    _SALTS.add_directory({'mode': MODES.TRENDING, 'section': section}, {'title': 'Trending %s' % (section_label)})
    if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.RECOMMEND, 'section': section}, {'title': 'Recommended %s' % (section_label)})
    if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.SHOW_FAVORITES, 'section': section}, {'title': 'My Favorites'})
    if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.MANAGE_SUBS, 'section': section}, {'title': 'My Subscriptions'})
    if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.SHOW_WATCHLIST, 'section': section}, {'title': 'My Watchlist'})
    if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.MY_LISTS, 'section': section}, {'title': 'My Lists'})
    _SALTS.add_directory({'mode': MODES.OTHER_LISTS, 'section': section}, {'title': 'Other Lists'})
    if section==SECTIONS.TV:
        if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.MY_CAL}, {'title': 'My Calendar'})
        _SALTS.add_directory({'mode': MODES.CAL}, {'title': 'General Calendar'})
        _SALTS.add_directory({'mode': MODES.PREMIERES}, {'title': 'Premiere Calendar'})
        if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.FRIENDS_EPISODE, 'section': section}, {'title': 'Friends Episode Activity'})
    if VALID_ACCOUNT: _SALTS.add_directory({'mode': MODES.FRIENDS, 'section': section}, {'title': 'Friends Activity'})
    _SALTS.add_directory({'mode': MODES.SEARCH, 'section': section}, {'title': 'Search'})
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.SCRAPERS)
def scraper_settings():
    scrapers=utils.relevant_scrapers(None, True, True)
    for i, cls in enumerate(scrapers):
        label = '%s (Provides: %s)' % (cls.get_name(), str(list(cls.provides())).replace("'", ""))
        if not utils.scraper_enabled(cls.get_name()): 
            label = '[COLOR darkred]%s[/COLOR]' % (label)
            toggle_label='Enable Scraper'
        else:
            toggle_label='Disable Scraper'
        liz = xbmcgui.ListItem(label=label)
        liz.setProperty('IsPlayable', 'false')
        liz.setInfo('video', {'title': label})
        liz_url = _SALTS.build_plugin_url({'mode': MODES.TOGGLE_SCRAPER, 'name': cls.get_name()})
        
        menu_items=[]
        if i>0:
            queries = {'mode': MODES.MOVE_SCRAPER, 'name': cls.get_name(), 'direction': DIRS.UP, 'other': scrapers[i-1].get_name()}
            menu_items.append(('Move Up', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
        if i<len(scrapers)-1:
            queries = {'mode': MODES.MOVE_SCRAPER, 'name': cls.get_name(), 'direction': DIRS.DOWN, 'other': scrapers[i+1].get_name()}
            menu_items.append(('Move Down', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )

        queries = {'mode': MODES.TOGGLE_SCRAPER, 'name': cls.get_name()}
        menu_items.append((toggle_label, 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
        liz.addContextMenuItems(menu_items, replaceItems=True)
        
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=False)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.MOVE_SCRAPER, ['name', 'direction', 'other'])
def move_scraper(name, direction, other):
    sort_key = utils.make_source_sort_key()
    if direction == DIRS.UP:
        sort_key[name] +=1
        sort_key[other] -= 1
    elif direction == DIRS.DOWN:
        sort_key[name] -= 1
        sort_key[other] += 1
    _SALTS.set_setting('source_sort_order', utils.make_source_sort_string(sort_key))
    xbmc.executebuiltin("XBMC.Container.Refresh")

@url_dispatcher.register(MODES.TOGGLE_SCRAPER, ['name'])
def toggle_scraper(name):
    if utils.scraper_enabled(name):
        setting='false'
    else:
        setting='true'
    _SALTS.set_setting('%s-enable' % (name), setting)
    xbmc.executebuiltin("XBMC.Container.Refresh")
    
@url_dispatcher.register(MODES.TRENDING, ['section'])
def browse_trending(section):
    list_data = trakt_api.get_trending(section)
    make_dir_from_list(section, list_data)

@url_dispatcher.register(MODES.RECOMMEND, ['section'])
def browse_recommendations(section):
    list_data = trakt_api.get_recommendations(section)
    make_dir_from_list(section, list_data)

@url_dispatcher.register(MODES.FRIENDS, ['mode', 'section'])
@url_dispatcher.register(MODES.FRIENDS_EPISODE, ['mode', 'section'])
def browse_friends(mode, section):
    section_params=utils.get_section_params(section, set_sort = False)
    activities=trakt_api.get_friends_activity(section, mode==MODES.FRIENDS_EPISODE)
    totalItems=len(activities)
    
    for activity in activities['activity']:
        if 'episode' in activity:
            show=activity['show']
            liz, liz_url = make_episode_item(show, activity['episode'], show['images']['fanart'], show_subs=False)
            folder=_SALTS.get_setting('source-win')=='Directory'
            label=liz.getLabel()
            label = '%s (%s) - %s' % (show['title'], show['year'], label)
            liz.setLabel(label) 
        else:
            liz, liz_url = make_item(section_params, activity[TRAKT_SECTIONS[section][:-1]])
            folder = section_params['folder']

        if not folder:
            liz.setProperty('IsPlayable', 'true')

        label=liz.getLabel()
        action = ' [[COLOR blue]%s[/COLOR] [COLOR green]%s' % (activity['user']['username'], activity['action'])
        if activity['action']=='rating': action += ' - %s' % (activity['rating'])
        action += '[/COLOR]]'
        label = '%s %s' % (action, label)
        liz.setLabel(label)
        
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz,isFolder=folder,totalItems=totalItems)        
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.MY_CAL, ['mode'], ['start_date'])
@url_dispatcher.register(MODES.CAL, ['mode'], ['start_date'])
@url_dispatcher.register(MODES.PREMIERES, ['mode'], ['start_date'])
def browse_calendar(mode, start_date=None):
    if start_date is None:
        now = datetime.datetime.now()
        offset = int(_SALTS.get_setting('calendar-day'))
        start_date = now + datetime.timedelta(days=offset)
        start_date = datetime.datetime.strftime(start_date,'%Y%m%d')
    if mode == MODES.MY_CAL:
        days=trakt_api.get_my_calendar(start_date)
    elif mode == MODES.CAL:
        days=trakt_api.get_calendar(start_date)
    elif mode == MODES.PREMIERES:
        days=trakt_api.get_premieres(start_date)
    make_dir_from_cal(mode, start_date, days)

@url_dispatcher.register(MODES.MY_LISTS, ['section'])
def browse_lists(section):
    lists = trakt_api.get_lists()
    lists.insert(0, {'name': 'watchlist', 'slug': utils.WATCHLIST_SLUG})
    totalItems=len(lists)
    for user_list in lists:
        liz = xbmcgui.ListItem(label=user_list['name'])
        queries = {'mode': MODES.SHOW_LIST, 'section': section, 'slug': user_list['slug']}
        liz_url = _SALTS.build_plugin_url(queries)
        
        menu_items=[]
        queries={'mode': MODES.SET_FAV_LIST, 'slug': user_list['slug'], 'section': section}
        menu_items.append(('Set as Favorites List', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
        queries={'mode': MODES.SET_SUB_LIST, 'slug': user_list['slug'], 'section': section}
        menu_items.append(('Set as Subscription List', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
        liz.addContextMenuItems(menu_items, replaceItems=True)
        
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz,isFolder=True,totalItems=totalItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.OTHER_LISTS, ['section'])
def browse_other_lists(section):
    liz = xbmcgui.ListItem(label='Add another user\'s list')
    liz_url = _SALTS.build_plugin_url({'mode': MODES.ADD_OTHER_LIST, 'section': section})
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=False)    
    
    lists = db_connection.get_other_lists(section)
    for other_list in lists:
        header, _ = trakt_api.show_list(other_list[1], section, other_list[0])
        _SALTS.add_directory({'mode': MODES.SHOW_LIST, 'section': section, 'slug': other_list[1], 'username': other_list[0]}, {'title': header['name']})
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    
@url_dispatcher.register(MODES.ADD_OTHER_LIST, ['section'])
def add_other_list(section):
    keyboard = xbmc.Keyboard()
    keyboard.setHeading('Enter username of list owner')
    keyboard.doModal()
    if keyboard.isConfirmed():
        username=keyboard.getText()
        slug=pick_list(None, section, username)
        if slug:
            db_connection.add_other_list(section, username, slug)
    xbmc.executebuiltin("XBMC.Container.Refresh")

@url_dispatcher.register(MODES.SHOW_LIST, ['section', 'slug'], ['username'])
def show_list(section, slug, username=None):
    if slug == utils.WATCHLIST_SLUG:
        items = trakt_api.show_watchlist(section)
    else:
        _, items = trakt_api.show_list(slug, section, username)
    make_dir_from_list(section, items, slug)

@url_dispatcher.register(MODES.SHOW_WATCHLIST, ['section'])
def show_watchlist(section):
    show_list(section, utils.WATCHLIST_SLUG)
    
@url_dispatcher.register(MODES.MANAGE_SUBS, ['section'])
def manage_subscriptions(section):
    slug=_SALTS.get_setting('%s_sub_slug' % (section))
    if slug:
        next_run = utils.get_next_run(MODES.UPDATE_SUBS)
        liz = xbmcgui.ListItem(label='Update Subscriptions: (Next Run: [COLOR green]%s[/COLOR])' % (next_run.strftime("%Y-%m-%d %H:%M:%S.%f")))
        liz_url = _SALTS.build_plugin_url({'mode': MODES.UPDATE_SUBS, 'section': section})
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=False)    
        if section == SECTIONS.TV:
            liz = xbmcgui.ListItem(label='Clean-Up Subscriptions')
            liz_url = _SALTS.build_plugin_url({'mode': MODES.CLEAN_SUBS})
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=False)    
    show_pickable_list(slug, 'Pick a list to use for Subscriptions', MODES.PICK_SUB_LIST, section)

@url_dispatcher.register(MODES.SHOW_FAVORITES, ['section'])
def show_favorites(section):
    slug=_SALTS.get_setting('%s_fav_slug' % (section))
    show_pickable_list(slug, 'Pick a list to use for Favorites', MODES.PICK_FAV_LIST, section)

@url_dispatcher.register(MODES.PICK_SUB_LIST, ['mode', 'section'])
@url_dispatcher.register(MODES.PICK_FAV_LIST, ['mode', 'section'])
def pick_list(mode, section, username=None):
    slug=utils.choose_list(username)
    if slug:
        if mode == MODES.PICK_FAV_LIST:
            set_list(MODES.SET_FAV_LIST, slug, section)
        elif mode == MODES.PICK_SUB_LIST:
            set_list(MODES.SET_SUB_LIST, slug, section)
        else:
            return slug
        xbmc.executebuiltin("XBMC.Container.Refresh")

@url_dispatcher.register(MODES.SET_SUB_LIST, ['mode', 'slug', 'section'])
@url_dispatcher.register(MODES.SET_FAV_LIST, ['mode', 'slug', 'section'])
def set_list(mode, slug, section):
    if mode == MODES.SET_FAV_LIST:
        setting='%s_fav_slug' % (section)
    elif mode == MODES.SET_SUB_LIST:
        setting='%s_sub_slug' % (section)
    _SALTS.set_setting(setting, slug)

@url_dispatcher.register(MODES.SEARCH, ['section'])
def search(section):
    keyboard = xbmc.Keyboard()
    keyboard.setHeading('Search %s' % (section))
    while True:
        keyboard.doModal()
        if keyboard.isConfirmed():
            search_text = keyboard.getText()
            if not search_text:
                _SALTS.show_ok_dialog(['Blank searches are not allowed'], title=_SALTS.get_name())
                continue
            else:
                break
        else:
            break
    
    if keyboard.isConfirmed():
        queries = {'mode': MODES.SEARCH_RESULTS, 'section': section, 'query': keyboard.getText()}
        pluginurl = _SALTS.build_plugin_url(queries)
        builtin = 'Container.Update(%s)' %(pluginurl)
        xbmc.executebuiltin(builtin)
    
@url_dispatcher.register(MODES.SEARCH_RESULTS, ['section', 'query'])
def search_results(section, query):
    section_params=utils.get_section_params(section)
    results = trakt_api.search(section, query)
    totalItems=len(results)
    for result in results:
        liz, liz_url = make_item(section_params, result)
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=section_params['folder'], totalItems=totalItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.SEASONS, ['slug', 'fanart'])
def browse_seasons(slug, fanart):
    seasons=trakt_api.get_seasons(slug)
    totalItems=len(seasons)
    for season in reversed(seasons):
        liz=utils.make_season_item(season, fanart)
        queries = {'mode': MODES.EPISODES, 'slug': slug, 'season': season['season'], 'fanart': fanart}
        liz_url = _SALTS.build_plugin_url(queries)
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz,isFolder=True,totalItems=totalItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.EPISODES, ['slug', 'season', 'fanart'])
def browse_episodes(slug, season, fanart):
    folder=_SALTS.get_setting('source-win')=='Directory'
    show=trakt_api.get_show_details(slug)
    episodes=trakt_api.get_episodes(slug, season)
    totalItems=len(episodes)
    for episode in episodes:
        liz, liz_url =make_episode_item(show, episode, fanart)
        if not folder:
            liz.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz,isFolder=folder,totalItems=totalItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

@url_dispatcher.register(MODES.GET_SOURCES, ['mode', 'video_type', 'title', 'year', 'slug'], ['season', 'episode', 'dialog'])
@url_dispatcher.register(MODES.SELECT_SOURCE, ['mode', 'video_type', 'title', 'year', 'slug'], ['season', 'episode'])
def get_sources(mode, video_type, title, year, slug, season='', episode='', dialog=None):
    timeout = max_timeout = int(_SALTS.get_setting('source_timeout'))
    if max_timeout == 0: timeout=None
    max_results = int(_SALTS.get_setting('source_results'))
    worker_count=0
    hosters=[]
    workers=[]
    if utils.P_MODE != P_MODES.NONE: q = utils.Queue()
    begin = time.time()
    
    for cls in utils.relevant_scrapers(video_type):
        if utils.P_MODE == P_MODES.NONE:
            hosters += cls(max_timeout).get_sources(video_type, title, year, season, episode)
            if max_results> 0 and len(hosters) >= max_results:
                break
        else:
            worker=utils.start_worker(q, utils.parallel_get_sources, [cls, video_type, title, year, season, episode])
            worker_count+=1
            workers.append(worker)

    # collect results from workers
    if utils.P_MODE != P_MODES.NONE:
        while worker_count>0:
            try:
                log_utils.log('Calling get with timeout: %s' %(timeout), xbmc.LOGDEBUG)
                result = q.get(True, timeout)
                log_utils.log('Got %s Source Results' %(len(result)), xbmc.LOGDEBUG)
                worker_count -=1
                hosters += result
                if max_timeout>0:
                    timeout = max_timeout - (time.time() - begin)
            except utils.Empty:
                log_utils.log('Get Sources Process Timeout', xbmc.LOGWARNING)
                break
            
            if max_results> 0 and len(hosters) >= max_results:
                log_utils.log('Exceeded max results: %s/%s' % (max_results, len(hosters)))
                break

        else:
            log_utils.log('All source results received')
        
    workers=utils.reap_workers(workers)
    try:
        if not hosters:
            log_utils.log('No Sources found for: |%s|%s|%s|%s|%s|' % (video_type, title, year, season, episode))
            builtin = 'XBMC.Notification(%s,No Sources Found, 5000, %s)'
            xbmc.executebuiltin(builtin % (_SALTS.get_name(), ICON_PATH))
            return False
        
        if _SALTS.get_setting('enable_sort')=='true':
            if _SALTS.get_setting('filter-unknown')=='true':
                hosters = utils.filter_hosters(hosters)
            SORT_KEYS['source'] = utils.make_source_sort_key()
            hosters.sort(key = utils.get_sort_key)
            
        global urlresolver
        import urlresolver
        if mode!=MODES.SELECT_SOURCE and _SALTS.get_setting('auto-play')=='true':
            auto_play_sources(hosters, video_type, slug, season, episode)
        else:
            if dialog or (dialog is None and _SALTS.get_setting('source-win') == 'Dialog'):
                stream_url = pick_source_dialog(hosters)
                return play_source(stream_url, video_type, slug, season, episode)
            else:
                pick_source_dir(hosters, video_type, slug, season, episode)
    finally:
        utils.reap_workers(workers, None)
    
@url_dispatcher.register(MODES.RESOLVE_SOURCE, ['class_url', 'video_type', 'slug', 'class_name'], ['season', 'episode'])
def resolve_source(class_url, video_type, slug, class_name, season='', episode=''):
    for cls in utils.relevant_scrapers(video_type):
        if cls.get_name() == class_name:
            scraper_instance=cls()
            break
    else:
        log_utils.log('Unable to locate scraper with name: %s' % (class_name))
        return False
        
    hoster_url = scraper_instance.resolve_link(class_url)
    return play_source(hoster_url, video_type, slug, season, episode)

def download_subtitles(language, title, year, season, episode):
    srt_scraper=SRT_Scraper()
    tvshow_id=srt_scraper.get_tvshow_id(title, year)
    if tvshow_id is None:
        return
     
    subs=srt_scraper.get_episode_subtitles(language, tvshow_id, season, episode)
    sub_labels=[]
    for sub in subs:
        sub_labels.append(utils.format_sub_label(sub))
     
    index=0
    if len(sub_labels)>1:
        dialog = xbmcgui.Dialog()       
        index = dialog.select('Choose a subtitle to download', sub_labels)
         
    if subs and index > -1:
        return srt_scraper.download_subtitle(subs[index]['url'])
    
def play_source(hoster_url, video_type, slug, season='', episode=''):
    if hoster_url is None:
        return False

    stream_url = urlresolver.HostedMediaFile(url=hoster_url).resolve()
    if not stream_url or not isinstance(stream_url, basestring):
        log_utils.log('Url (%s) Resolution failed' % (hoster_url))
        builtin = 'XBMC.Notification(%s,Could not Resolve Url: %s, 5000, %s)'
        xbmc.executebuiltin(builtin % (_SALTS.get_name(), hoster_url, ICON_PATH))
        return False

    try:
        art={'thumb': '', 'fanart': ''}
        info={}
        if video_type == VIDEO_TYPES.EPISODE:
            details = trakt_api.get_episode_details(slug, season, episode)
            info = utils.make_info(details['episode'], details['show'])
            art=utils.make_art(details['episode'], details['show']['images']['fanart'])
        else:
            item = trakt_api.get_movie_details(slug)
            info = utils.make_info(item)
            art=utils.make_art(item)
    except TransientTraktError as e:
        log_utils.log('During Playback: %s' % (str(e)), xbmc.LOGWARNING) # just log warning if trakt calls fail and leave meta and art blank
    
    if video_type == VIDEO_TYPES.EPISODE and utils.srt_download_enabled():
        srt_path = download_subtitles(_SALTS.get_setting('subtitle-lang'), details['show']['title'], details['show']['year'], season, episode)
        if utils.srt_show_enabled() and srt_path:
            log_utils.log('Setting srt path: %s' % (srt_path), xbmc.LOGDEBUG)
            win = xbmcgui.Window(10000)
            win.setProperty('salts.playing.srt', srt_path)

    listitem = xbmcgui.ListItem(path=stream_url, iconImage=art['thumb'], thumbnailImage=art['thumb'])
    listitem.setProperty('fanart_image', art['fanart'])
    try: listitem.setArt(art)
    except:pass
    listitem.setProperty('IsPlayable', 'true')
    listitem.setPath(stream_url)
    listitem.setInfo('video', info)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)
    
    return True

def auto_play_sources(hosters, video_type, slug, season, episode):
    for item in hosters:
        # TODO: Skip multiple sources for now
        if item['multi-part']:
            continue

        hoster_url=item['class'].resolve_link(item['url'])
        log_utils.log('Auto Playing: %s' % (hoster_url), xbmc.LOGDEBUG)
        if play_source(hoster_url, video_type, slug, season, episode):
            return True

def pick_source_dialog(hosters, filtered=False):
    for item in hosters:
        # TODO: Skip multiple sources for now
        if item['multi-part']:
            continue

        if filtered:
            hosted_media = urlresolver.HostedMediaFile(host=item['host'], media_id='dummy') # use dummy media_id to force host validation
            if not hosted_media:
                log_utils.log('Skipping unresolvable source: %s (%s)' % (item['url'], item['host']))
                continue
        
        label = item['class'].format_source_label(item)
        label = '[%s] %s' % (item['class'].get_name(),label)
        item['label']=label
    
    dialog = xbmcgui.Dialog() 
    index = dialog.select('Choose your stream', [item['label'] for item in hosters if 'label' in item])
    if index>-1:
        try:
            hoster_url=hosters[index]['class'].resolve_link(hosters[index]['url'])
            log_utils.log('Attempting to play url: %s' % hoster_url)
            return hoster_url
        except Exception as e:
            log_utils.log('Error (%s) while trying to resolve %s' % (str(e), hoster_url), xbmc.LOGERROR)
            return False
    else:
        return None
    
def pick_source_dir(hosters, video_type, slug, season='', episode='', filtered=False):
    for item in hosters:
        # TODO: Skip multiple sources for now
        if item['multi-part']:
            continue

        if filtered:
            hosted_media = urlresolver.HostedMediaFile(host=item['host'], media_id='dummy') # use dummy media_id to force host validation
            if not hosted_media:
                log_utils.log('Skipping unresolvable source: %s (%s)' % (item['url'], item['host']))
                continue
        
        label = item['class'].format_source_label(item)
        label = '[%s] %s' % (item['class'].get_name(),label)
        item['label']=label
    
    hosters_len=len(hosters)
    for item in hosters:
        #log_utils.log(item, xbmc.LOGDEBUG)
        queries={'mode': MODES.RESOLVE_SOURCE, 'class_url': item['url'], 'video_type': video_type, 'slug': slug, 'season': season, 'episode': episode, 'class_name': item['class'].get_name()}
        _SALTS.add_directory(queries, infolabels={'title': item['label']}, is_folder=False, img='', fanart='', total_items=hosters_len)
    
    _SALTS.end_of_directory()

@url_dispatcher.register(MODES.SET_URL_MANUAL, ['mode', 'video_type', 'title', 'year'], ['season', 'episode'])
@url_dispatcher.register(MODES.SET_URL_SEARCH, ['mode', 'video_type', 'title', 'year'], ['season', 'episode'])
def set_related_url(mode, video_type, title, year, season='', episode=''):
    related_list=[]
    timeout = max_timeout = int(_SALTS.get_setting('source_timeout'))
    if max_timeout == 0: timeout=None
    worker_count=0
    workers=[]
    if utils.P_MODE != P_MODES.NONE: q = utils.Queue()
    begin = time.time()
    for cls in utils.relevant_scrapers(video_type):
        if utils.P_MODE == P_MODES.NONE:
            related={}
            related['class']=cls(max_timeout)
            url=related['class'].get_url(video_type, title, year, season, episode)
            if not url: url=''
            related['url']=url
            related['name']=related['class'].get_name()
            related['label'] = '[%s] %s' % (related['name'], related['url'])
            related_list.append(related)
        else:
            worker = utils.start_worker(q, utils.parallel_get_url, [cls, video_type, title, year, season, episode])
            worker_count += 1
            workers.append(worker)
    
    # collect results from workers
    if utils.P_MODE != P_MODES.NONE:
        while worker_count>0:
            try:
                log_utils.log('Calling get with timeout: %s' %(timeout), xbmc.LOGDEBUG)
                result = q.get(True, timeout)
                log_utils.log('Got result: %s' %(result), xbmc.LOGDEBUG)
                related_list.append(result)
                worker_count -=1
                if max_timeout>0:
                    timeout = max_timeout - (time.time() - begin)
            except utils.Empty:
                log_utils.log('Get Url Timeout', xbmc.LOGWARNING)
                break
        else:
            log_utils.log('All source results received')

    workers=utils.reap_workers(workers)
    try:
        dialog=xbmcgui.Dialog()
        index = dialog.select('Url To Change (%s)' % (video_type), [related['label'] for related in related_list])
        if index>-1:
            if mode == MODES.SET_URL_MANUAL:
                keyboard = xbmc.Keyboard()
                keyboard.setHeading('Related %s url at %s' % (video_type, related_list[index]['name']))
                keyboard.setDefault(related_list[index]['url'])
                keyboard.doModal()
                if keyboard.isConfirmed():
                    new_url = keyboard.getText()
                    utils.update_url(video_type, title, year, related_list[index]['name'], related_list[index]['url'], new_url, season, episode)
                    builtin = 'XBMC.Notification(%s,[COLOR blue]%s[/COLOR] Related Url Set, 5000, %s)'
                    xbmc.executebuiltin(builtin % (_SALTS.get_name(), related_list[index]['name'], ICON_PATH))
            elif mode == MODES.SET_URL_SEARCH:
                temp_title = title
                temp_year = year
                while True:
                    dialog=xbmcgui.Dialog()
                    choices = ['Manual Search']
                    try:
                        log_utils.log('Searching for: |%s|%s|' % (temp_title, temp_year), xbmc.LOGDEBUG)
                        results = related_list[index]['class'].search(video_type, temp_title, temp_year)
                        for result in results:
                            choice = result['title']
                            if result['year']: choice = '%s (%s)' % (choice, result['year'])
                            choices.append(choice)
                        results_index = dialog.select('Select Related', choices)
                        if results_index==0:
                            keyboard = xbmc.Keyboard()
                            keyboard.setHeading('Enter Search')
                            text = temp_title
                            if temp_year: text = '%s (%s)' % (text, temp_year)
                            keyboard.setDefault(text)
                            keyboard.doModal()
                            if keyboard.isConfirmed():
                                match = re.match('([^\(]+)\s*\(*(\d{4})?\)*', keyboard.getText())
                                temp_title = match.group(1).strip()
                                temp_year = match.group(2) if match.group(2) else '' 
                        elif results_index>0:
                            utils.update_url(video_type, title, year, related_list[index]['name'], related_list[index]['url'], results[results_index-1]['url'], season, episode)
                            builtin = 'XBMC.Notification(%s,[COLOR blue]%s[/COLOR] Related Url Set, 5000, %s)'
                            xbmc.executebuiltin(builtin % (_SALTS.get_name(), related_list[index]['name'], ICON_PATH))
                            break
                        else:
                            break
                    except NotImplementedError:
                        log_utils.log('%s Scraper does not support searching.' % (related_list[index]['class'].get_name()))
                        builtin = 'XBMC.Notification(%s,%s Scraper does not support searching, 5000, %s)'
                        xbmc.executebuiltin(builtin % (_SALTS.get_name(), related_list[index]['class'].get_name(), ICON_PATH))
                        break
    finally:
        utils.reap_workers(workers, None)

@url_dispatcher.register(MODES.EDIT_TVSHOW_ID, ['title'], ['year'])
def edit_tvshow_id(title, year=''):
    srt_scraper=SRT_Scraper()
    tvshow_id=srt_scraper.get_tvshow_id(title, year)
    keyboard = xbmc.Keyboard()
    keyboard.setHeading('Input TVShow ID')
    if tvshow_id:
        keyboard.setDefault(str(tvshow_id))
    keyboard.doModal()
    if keyboard.isConfirmed():
        db_connection.set_related_url(VIDEO_TYPES.TVSHOW, title, year, SRT_SOURCE, keyboard.getText())
                
@url_dispatcher.register(MODES.REM_FROM_LIST, ['slug', 'section', 'id_type', 'show_id'])
def remove_from_list(slug, section, id_type, show_id):
    item={'type': TRAKT_SECTIONS[section][:-1], id_type: show_id}
    if slug==utils.WATCHLIST_SLUG:
        trakt_api.remove_from_watchlist(section, item)
    else:
        trakt_api.remove_from_list(slug, item)
    xbmc.executebuiltin("XBMC.Container.Refresh")
    
@url_dispatcher.register(MODES.ADD_TO_LIST, ['section', 'id_type', 'show_id'], ['slug'])
def add_to_list(section, id_type, show_id, slug=None):
    item={'type': TRAKT_SECTIONS[section][:-1], id_type: show_id}
    if not slug: slug=utils.choose_list()
    if slug==utils.WATCHLIST_SLUG:
        trakt_api.add_to_watchlist(section, item)
    elif slug:
        trakt_api.add_to_list(slug, item)
    builtin = "XBMC.Notification(%s,Item Added to List, 2000, %s)" % (_SALTS.get_name(), ICON_PATH)
    xbmc.executebuiltin(builtin)
    xbmc.executebuiltin("XBMC.Container.Refresh")

@url_dispatcher.register(MODES.UPDATE_SUBS)
def update_subscriptions():
    log_utils.log('Updating Subscriptions', xbmc.LOGDEBUG)
    if _SALTS.get_setting(MODES.UPDATE_SUBS+'-notify')=='true':
        builtin = "XBMC.Notification(%s,Subscription Update Started, 2000, %s)" % (_SALTS.get_name(), ICON_PATH)
        xbmc.executebuiltin(builtin)

    update_strms(SECTIONS.TV)
    if _SALTS.get_setting('include_movies') == 'true':
        update_strms(SECTIONS.MOVIES)
    if _SALTS.get_setting('library-update') == 'true':
        xbmc.executebuiltin('UpdateLibrary(video)')
    if _SALTS.get_setting('cleanup-subscriptions') == 'true':
        clean_subs()

    now = datetime.datetime.now()
    db_connection.set_setting('%s-last_run' % MODES.UPDATE_SUBS, now.strftime("%Y-%m-%d %H:%M:%S.%f"))

    if _SALTS.get_setting(MODES.UPDATE_SUBS+'-notify')=='true':
        builtin = "XBMC.Notification(%s,Subscriptions Updated, 2000, %s)" % (_SALTS.get_name(), ICON_PATH)
        xbmc.executebuiltin(builtin)
        builtin = "XBMC.Notification(%s,Next Update in %0.1f hours,5000, %s)" % (_SALTS.get_name(), float(_SALTS.get_setting(MODES.UPDATE_SUBS+'-interval')), ICON_PATH)
        xbmc.executebuiltin(builtin)
    xbmc.executebuiltin("XBMC.Container.Refresh")
    
def update_strms(section):
    section_params = utils.get_section_params(section)
    slug=_SALTS.get_setting('%s_sub_slug' % (section))
    if not slug:
        return
    elif slug == utils.WATCHLIST_SLUG:
        items = trakt_api.show_watchlist(section)
    else:
        _, items = trakt_api.show_list(slug, section)
    
    for item in items:
        add_to_library(section_params['video_type'], item['title'], item['year'], trakt_api.get_slug(item['url']), require_source=True)

@url_dispatcher.register(MODES.CLEAN_SUBS)
def clean_subs():
    slug=_SALTS.get_setting('TV_sub_slug')
    if not slug:
        return
    elif slug == utils.WATCHLIST_SLUG:
        items = trakt_api.show_watchlist(SECTIONS.TV)
    else:
        _, items = trakt_api.show_list(slug, SECTIONS.TV)
    
    for item in items:
        show_slug=trakt_api.get_slug(item['url'])
        show=trakt_api.get_show_details(show_slug)
        if show['status'].upper()=='ENDED':
            del_item = {'type': TRAKT_SECTIONS[SECTIONS.TV][:-1]}
            if 'imdb_id' in show:
                show_id={'imdb_id': show['imdb_id']}
            elif 'tvdb_id' in show:
                show_id={'tvdb_id': show['tvdb_id']}
            else:
                show_id={'title': show['title'], 'year': show['year']}
            del_item.update(show_id)
            
            if slug == utils.WATCHLIST_SLUG:
                trakt_api.remove_from_watchlist(SECTIONS.TV, del_item)
            else:
                trakt_api.remove_from_list(slug, del_item)

@url_dispatcher.register(MODES.FLUSH_CACHE)
def flush_cache():
    dlg = xbmcgui.Dialog()
    ln1 = 'Are you sure you want to delete the url cache?'
    ln2 = 'This will slow things down until rebuilt'
    ln3 = ''
    yes = 'Keep'
    no = 'Delete'
    if dlg.yesno('Flush web cache', ln1, ln2, ln3, yes, no):
        db_connection.flush_cache()

@url_dispatcher.register(MODES.RESET_DB)
def reset_db():
    if db_connection.reset_db():
        message='DB Reset Successful'
    else:
        message='Reset only allowed on sqlite DBs'
    
    builtin = "XBMC.Notification(PrimeWire,%s,2000, %s)" % (message, ICON_PATH)
    xbmc.executebuiltin(builtin)        

@url_dispatcher.register(MODES.ADD_TO_LIBRARY, ['video_type', 'title', 'year', 'slug'])
def add_to_library(video_type, title, year, slug, require_source=False):
    log_utils.log('Creating .strm for |%s|%s|%s|%s|' % (video_type, title, year, slug), xbmc.LOGDEBUG)
    if video_type == VIDEO_TYPES.TVSHOW:
        save_path = _SALTS.get_setting('tvshow-folder')
        save_path = xbmc.translatePath(save_path)
        show = trakt_api.get_show_details(slug)
        seasons = trakt_api.get_seasons(slug)

        if not seasons:
            log_utils.log('No Seasons found for %s (%s)' % (show['title'], show['year']), xbmc.LOGERROR)

        for season in reversed(seasons):
            season_num = season['season']
            episodes = trakt_api.get_episodes(slug, season_num)
            for episode in episodes:
                ep_num = episode['episode']
                filename = utils.filename_from_title(show['title'], video_type)
                filename = filename % ('%02d' % int(season_num), '%02d' % int(ep_num))
                final_path = os.path.join(save_path, show['title'], 'Season %s' % (season_num), filename)
                strm_string = _SALTS.build_plugin_url({'mode': MODES.GET_SOURCES, 'video_type': VIDEO_TYPES.EPISODE, 'title': title, 'year': year, 'season': season_num, 'episode': ep_num, 'slug': slug, 'dialog': True})
                write_strm(strm_string, final_path, VIDEO_TYPES.EPISODE, title, year, season_num, ep_num, require_source)
                
    elif video_type == VIDEO_TYPES.MOVIE:
        save_path = _SALTS.get_setting('movie-folder')
        save_path = xbmc.translatePath(save_path)
        strm_string = _SALTS.build_plugin_url({'mode': MODES.GET_SOURCES, 'video_type': video_type, 'title': title, 'year': year, 'slug': slug, 'dialog': True})
        filename = utils.filename_from_title(title, VIDEO_TYPES.MOVIE, year)
        dir_name = title if not year else '%s (%s)' % (title, year)
        final_path = os.path.join(save_path, dir_name, filename)
        write_strm(strm_string, final_path, VIDEO_TYPES.MOVIE, title, year, require_source=require_source)

def write_strm(stream, path, video_type, title, year, season='', episode='', require_source=False):
    path = xbmc.makeLegalFilename(path)
    if not xbmcvfs.exists(os.path.dirname(path)):
        try:
            try: xbmcvfs.mkdirs(os.path.dirname(path))
            except: os.mkdir(os.path.dirname(path))
        except:
            log_utils.log('Failed to create directory %s' % path, xbmc.LOGERROR)

    old_strm_string=''
    try:
        f = xbmcvfs.File(path, 'r')
        old_strm_string = f.read()
        f.close()
    except:  pass
    
    #print "Old String: %s; New String %s" %(old_strm_string,strm_string)
    # string will be blank if file doesn't exist or is blank
    if stream != old_strm_string:
        try:
            if not require_source or utils.url_exists(video_type, title, year, season, episode):
                log_utils.log('Writing strm: %s' % stream)
                file_desc = xbmcvfs.File(path, 'w')
                file_desc.write(stream)
                file_desc.close()
            else:
                log_utils.log('No strm written for |%s|%s|%s|%s|%s|' % (video_type, title, year, season, episode), xbmc.LOGWARNING)
        except Exception, e:
            log_utils.log('Failed to create .strm file: %s\n%s' % (path, e), xbmc.LOGERROR)
    
def show_pickable_list(slug, pick_label, pick_mode, section):
    if not slug:
        liz = xbmcgui.ListItem(label=pick_label)
        liz_url = _SALTS.build_plugin_url({'mode': pick_mode, 'section': section})
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=False)    
        xbmcplugin.endOfDirectory(int(sys.argv[1]))
    else:
        show_list(section, slug)

def make_dir_from_list(section, list_data, slug=None):
    section_params=utils.get_section_params(section)
    totalItems=len(list_data)
    for show in list_data:
        menu_items=[]
        if slug:
            queries = {'mode': MODES.REM_FROM_LIST, 'slug': slug, 'section': section}
            queries.update(utils.show_id(show))
            menu_items.append(('Remove from List', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
        sub_slug=_SALTS.get_setting('%s_sub_slug' % (section))
        if VALID_ACCOUNT and sub_slug and sub_slug != slug:
            queries = {'mode': MODES.ADD_TO_LIST, 'section': section_params['section'], 'slug': sub_slug}
            queries.update(utils.show_id(show))
            menu_items.append(('Subscribe', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )

        liz, liz_url =make_item(section_params, show, menu_items)
        
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=section_params['folder'], totalItems=totalItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

def make_dir_from_cal(mode, start_date, days):
    try: start_date=datetime.datetime.strptime(start_date,'%Y%m%d')
    except TypeError: start_date = datetime.datetime(*(time.strptime(start_date, '%Y%m%d')[0:6]))
    last_week = start_date - datetime.timedelta(days=7)
    next_week = start_date + datetime.timedelta(days=7)
    last_week = datetime.datetime.strftime(last_week, '%Y%m%d')
    next_week = datetime.datetime.strftime(next_week, '%Y%m%d')
    
    liz = xbmcgui.ListItem(label='<< Previous Week')
    liz_url = _SALTS.build_plugin_url({'mode': mode, 'start_date': last_week})
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=True)
    
    totalItems=len(days)
    for day in days:
        date=utils.make_day(day['date'])
        for episode_elem in day['episodes']:
            show=episode_elem['show']
            episode=episode_elem['episode']
            fanart=show['images']['fanart']
            liz, liz_url =make_episode_item(show, episode, fanart, show_subs=False)
            label=liz.getLabel()
            label = '[[COLOR deeppink]%s[/COLOR]] %s - %s' % (date, show['title'], label.decode('utf-8', 'replace'))
            if episode['season']==1 and episode['number']==1:
                label = '[COLOR green]%s[/COLOR]' % (label)
            liz.setLabel(label)
            liz.setProperty('isPlayable', 'true')
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz,isFolder=False,totalItems=totalItems)

    liz = xbmcgui.ListItem(label='Next Week >>')
    liz_url = _SALTS.build_plugin_url({'mode': mode, 'start_date': next_week})
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), liz_url, liz, isFolder=True)    
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

def make_episode_item(show, episode, fanart, show_subs=True):
    show['title']=re.sub(' \(\d{4}\)$','',show['title'])
    if 'episode' in episode: episode_num=episode['episode']
    else:  episode_num=episode['number']
    label = '%sx%s %s' % (episode['season'], episode_num, episode['title'])
    if show_subs and utils.srt_indicators_enabled():
        srt_scraper=SRT_Scraper()
        language=_SALTS.get_setting('subtitle-lang')
        tvshow_id=srt_scraper.get_tvshow_id(show['title'], show['year'])
        if tvshow_id is not None:
            srts=srt_scraper.get_episode_subtitles(language, tvshow_id, episode['season'], episode_num)
        else:
            srts=[]
        label = utils.format_episode_label(label, episode['season'], episode_num, srts)
            
    meta=utils.make_info(episode, show)
    meta['images']={}
    meta['images']['poster']=episode['images']['screen']
    meta['images']['fanart']=fanart
    if 'watched' in episode and episode['watched']: meta['playcount']=1
    liz=utils.make_list_item(label, meta)
    del meta['images']
    liz.setInfo('video', meta)
    queries = {'mode': MODES.GET_SOURCES, 'video_type': VIDEO_TYPES.EPISODE, 'title': show['title'], 'year': show['year'], 'season': episode['season'], 'episode': episode_num, 
               'slug': trakt_api.get_slug(show['url'])}
    liz_url = _SALTS.build_plugin_url(queries)
    
    menu_items=[]
    if _SALTS.get_setting('auto-play')=='true':
        queries = {'mode': MODES.SELECT_SOURCE, 'video_type': VIDEO_TYPES.EPISODE, 'title': show['title'], 'year': show['year'], 'season': episode['season'], 'episode': episode_num, 'slug': trakt_api.get_slug(show['url'])}
        if _SALTS.get_setting('source-win')=='Dialog':
            runstring = 'RunPlugin(%s)' % _SALTS.build_plugin_url(queries)
        else:
            runstring = 'Container.Update(%s)' % _SALTS.build_plugin_url(queries)
        menu_items.append(('Select Source', runstring), )
        
    menu_items.append(('Show Information', 'XBMC.Action(Info)'), )
    queries = {'mode': MODES.SET_URL_MANUAL, 'video_type': VIDEO_TYPES.EPISODE, 'title': show['title'], 'year': show['year'], 'season': episode['season'], 'episode': episode_num}
    menu_items.append(('Set Related Url (Manual)', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
    liz.addContextMenuItems(menu_items, replaceItems=True)
    return liz, liz_url

def make_item(section_params, show, menu_items=None):
    if menu_items is None: menu_items=[]
    show['title']=re.sub(' \(\d{4}\)$','',show['title'])
    label = '%s (%s)' % (show['title'], show['year'])
    liz=utils.make_list_item(label, show)
    slug=trakt_api.get_slug(show['url'])
    liz.setProperty('slug', slug)
    info = utils.make_info(show)
    if not section_params['folder']:
        liz.setProperty('IsPlayable', 'true')
 
    if section_params['section']==SECTIONS.TV:
        queries = {'mode': section_params['next_mode'], 'slug': slug, 'fanart': liz.getProperty('fanart_image')}
        if 'playcount' in info: del info['playcount'] # remove playcount from tv shows
        info['TVShowTitle']=info['title']
    else:
        queries = {'mode': section_params['next_mode'], 'video_type': section_params['video_type'], 'title': show['title'], 'year': show['year'], 'slug': slug}
 
    liz.setInfo('video', info)
    liz_url = _SALTS.build_plugin_url(queries)
 
    if section_params['next_mode']==MODES.GET_SOURCES and _SALTS.get_setting('auto-play')=='true':
        queries = {'mode': MODES.SELECT_SOURCE, 'video_type': section_params['video_type'], 'title': show['title'], 'year': show['year'], 'slug': slug}
        if _SALTS.get_setting('source-win')=='Dialog':
            runstring = 'RunPlugin(%s)' % _SALTS.build_plugin_url(queries)
        else:
            runstring = 'Container.Update(%s)' % _SALTS.build_plugin_url(queries)
        menu_items.insert(0, ('Select Source', runstring), )
        
    menu_items.append(('Show Information', 'XBMC.Action(Info)'), )
    if VALID_ACCOUNT:
        queries = {'mode': MODES.ADD_TO_LIST, 'section': section_params['section']}
        queries.update(utils.show_id(show))
        menu_items.append(('Add to List', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
    queries = {'mode': MODES.ADD_TO_LIBRARY, 'video_type': section_params['video_type'], 'title': show['title'], 'year': show['year'], 'slug': slug}
    menu_items.append(('Add to Library', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )

    if section_params['section']==SECTIONS.TV and _SALTS.get_setting('enable-subtitles')=='true':
        queries = {'mode': MODES.EDIT_TVSHOW_ID, 'title': show['title'], 'year': show['year']}
        runstring = 'RunPlugin(%s)' % _SALTS.build_plugin_url(queries)
        menu_items.append(('Set Addic7ed TVShowID', runstring,))

    queries = {'mode': MODES.SET_URL_SEARCH, 'video_type': section_params['video_type'], 'title': show['title'], 'year': show['year']}
    menu_items.append(('Set Related Url (Search)', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
    queries = {'mode': MODES.SET_URL_MANUAL, 'video_type': section_params['video_type'], 'title': show['title'], 'year': show['year']}
    menu_items.append(('Set Related Url (Manual)', 'RunPlugin(%s)' % (_SALTS.build_plugin_url(queries))), )
    liz.addContextMenuItems(menu_items, replaceItems=True)
 
    return liz, liz_url

def main(argv=None):
    if sys.argv: argv=sys.argv

    log_utils.log('Version: |%s| Queries: |%s|' % (_SALTS.get_version(),_SALTS.queries))
    log_utils.log('Args: |%s|' % (argv))
    
    # don't process params that don't match our url exactly. (e.g. plugin://plugin.video.1channel/extrafanart)
    plugin_url = 'plugin://%s/' % (_SALTS.get_id())
    if argv[0] != plugin_url:
        return

    try:
        mode = _SALTS.queries.get('mode', None)
        url_dispatcher.dispatch(mode, _SALTS.queries)
    except TransientTraktError as e:
        log_utils.log(str(e), xbmc.LOGERROR)
        builtin = 'XBMC.Notification(%s,%s, 5000, %s)'
        xbmc.executebuiltin(builtin % (_SALTS.get_name(), str(e), ICON_PATH))

if __name__ == '__main__':
    sys.exit(main())
